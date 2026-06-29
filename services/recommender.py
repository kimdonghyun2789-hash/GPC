"""
services/recommender.py
오늘의 점심 1·2·3순위 추천 엔진(핵심).
- 비활성/블랙리스트/방문불가/휴무/도보초과/최근방문/카테고리중복/예산 필터링
- 선호도·거리·가격·혼잡도·예산·방문횟수·최근미방문·자연어요청·랜덤 점수 합산
- 후보 부족 시 조건 단계적 완화(PRD 12.7)
- AI는 코멘트 생성에만 사용하며, 기본 추천은 AI 없이도 동작한다.
"""

from __future__ import annotations

import random

from services import db, ai_analyzer
from utils import date_utils, score_utils

# 상황별 추천 모드 (PRD 3.8) -> 추천 힌트로 변환
RECOMMEND_MODES = {
    "빠른 점심": {"prefer_short_walk": True, "keywords": ["분식", "국밥", "백반"]},
    "든든하게": {"keywords": ["한식", "백반", "돈까스", "국밥"]},
    "가성비": {"prefer_cheap": True},
    "새로운 곳": {"prefer_new": True},
    "해장": {"keywords": ["국밥", "해장", "순대"]},
    "국물": {"keywords": ["국밥", "찌개", "라멘", "쌀국수", "냉면"]},
    "면": {"keywords": ["라멘", "쌀국수", "냉면", "국수"]},
    "가까운 곳": {"prefer_short_walk": True},
    "돈 아끼는 날": {"prefer_cheap": True},
}


def _hint_from_mode(mode: str) -> dict | None:
    """모드 이름을 추천 힌트 dict로 변환한다."""
    spec = RECOMMEND_MODES.get(mode)
    if not spec:
        return None
    return {
        "keywords": list(spec.get("keywords", [])),
        "prefer_short_walk": spec.get("prefer_short_walk", False),
        "prefer_cheap": spec.get("prefer_cheap", False),
        "prefer_new": spec.get("prefer_new", False),
        "avoid_categories": [],
        "raw": mode,
    }


def _merge_hints(a: dict | None, b: dict | None) -> dict | None:
    """두 힌트를 병합한다(자연어 요청 + 모드)."""
    if not a:
        return b
    if not b:
        return a
    return {
        "keywords": list(dict.fromkeys(a.get("keywords", []) + b.get("keywords", []))),
        "avoid_categories": list(dict.fromkeys(a.get("avoid_categories", []) + b.get("avoid_categories", []))),
        "prefer_short_walk": a.get("prefer_short_walk") or b.get("prefer_short_walk"),
        "prefer_cheap": a.get("prefer_cheap") or b.get("prefer_cheap"),
        "prefer_new": a.get("prefer_new") or b.get("prefer_new"),
        "raw": " / ".join(x for x in [a.get("raw"), b.get("raw")] if x),
    }


def _passes_hard_filters(rest, today, max_walk, unavailable_ids):
    """완화 불가능한 기본(하드) 필터. 통과하면 True."""
    if not rest.get("is_active"):
        return False
    if rest.get("is_blacklisted"):
        # 블랙리스트 해제일이 지났는지 확인
        until = rest.get("blacklist_until")
        if not until or date_utils.to_date(until) >= today:
            return False
    if rest["id"] in unavailable_ids:
        return False
    if rest.get("status") == "폐업 의심":  # PRD 3.10: 기본 추천 제외
        return False
    if not date_utils.is_open_today(rest.get("open_days"), today):
        return False
    return True


def _score_restaurant(rest, settings, today, last_visit_map, count_map,
                      meal_budget, budget_mode, hint, relax_level, sat_map=None):
    """
    단일 식당의 최종 점수와 사유를 계산한다.
    예산 '제외' 모드에서 초과 식당은 None을 반환(후보 제외).
    relax_level은 후보 부족 시 완화 단계(0=완화없음).
    반환: (score: float, reasons: list[str], breakdown: dict) 또는 None
    """
    w = {
        "preference": settings.get("weight_preference", 1.0),
        "distance": settings.get("weight_distance", 1.0),
        "price": settings.get("weight_price", 1.0),
        "crowd": settings.get("weight_crowd", 1.0),
        "budget": settings.get("weight_budget", 1.0),
    }
    max_walk = settings.get("max_walk_minutes", 10)
    exclude_recent = settings.get("exclude_recent_days", 5)

    # 최근 방문일 -> 경과일수
    last_date = last_visit_map.get(rest["id"])
    last_days = date_utils.days_between(today, last_date) if last_date else None

    s_pref = score_utils.preference_score(rest.get("rating")) * w["preference"]
    s_dist = score_utils.distance_score(rest.get("walk_minutes"), max_walk) * w["distance"]
    s_price = score_utils.price_score(rest.get("avg_price"), meal_budget) * w["price"]
    s_crowd = score_utils.crowd_score(rest.get("crowd_level")) * w["crowd"]
    s_recency = score_utils.recency_score(last_days, exclude_recent)
    s_visits = score_utils.visit_count_score(count_map.get(rest["id"], 0))
    avg_sat = (sat_map or {}).get(rest["id"])
    s_satisfaction = score_utils.satisfaction_score(avg_sat)

    # 예산 점수 (relax_level>=5면 '제외'를 '감점'으로 완화)
    effective_mode = budget_mode
    if relax_level >= 5 and budget_mode == "제외":
        effective_mode = "감점"
    s_budget = score_utils.budget_score(rest.get("avg_price"), meal_budget, effective_mode)
    if s_budget is None:
        return None  # 예산 초과 제외
    s_budget *= w["budget"]

    # 자연어 요청 반영 점수 (+ 신규 식당 선호 모드)
    s_request = _request_bonus(rest, hint)
    if hint and hint.get("prefer_new") and last_days is None:
        s_request += 8.0

    # 자주 만석 식당 점심 피크 감점 (PRD 3.10)
    s_peak = -8.0 if rest.get("is_frequent_full") else 0.0
    s_request += s_peak

    # 랜덤 점수
    random_weight = settings.get("random_weight", 10)
    s_random = random.uniform(0, random_weight)

    total = round(
        s_pref + s_dist + s_price + s_crowd + s_recency + s_visits
        + s_satisfaction + s_budget + s_request + s_random,
        2,
    )

    reasons = _build_reasons(rest, last_days, meal_budget, exclude_recent, hint, avg_sat)
    breakdown = {
        "선호도": round(s_pref, 1), "거리": round(s_dist, 1), "가격": round(s_price, 1),
        "혼잡도": round(s_crowd, 1), "예산": round(s_budget, 1), "최근미방문": round(s_recency, 1),
        "방문횟수": round(s_visits, 1), "내만족도": round(s_satisfaction, 1),
        "요청반영": round(s_request, 1), "랜덤": round(s_random, 1),
    }
    return total, reasons, breakdown


def _request_bonus(rest, hint) -> float:
    """자연어 요청 힌트를 점수로 환산한다."""
    if not hint:
        return 0.0
    bonus = 0.0
    cat = str(rest.get("category") or "")
    menu = f"{rest.get('main_menu') or ''} {rest.get('sub_menu') or ''}"
    tags = " ".join(rest.get("tags") or [])

    for kw in hint.get("keywords", []):
        if kw and (kw in cat or kw in menu or kw in tags):
            bonus += 6.0
    for avoid in hint.get("avoid_categories", []):
        if avoid and (avoid in cat):
            bonus -= 8.0
    if hint.get("prefer_short_walk"):
        try:
            if float(rest.get("walk_minutes", 99)) <= 5:
                bonus += 5.0
        except (TypeError, ValueError):
            pass
    if hint.get("prefer_cheap"):
        try:
            if float(rest.get("avg_price", 0)) <= 10000:
                bonus += 5.0
        except (TypeError, ValueError):
            pass
    return bonus


def _build_reasons(rest, last_days, meal_budget, exclude_recent, hint, avg_sat=None) -> list[str]:
    """추천 사유 문구 리스트를 만든다."""
    reasons = []
    if avg_sat is not None and avg_sat >= 4.0:
        reasons.append(f"내 만족도가 높았던 곳 (★{avg_sat:.1f})")
    if last_days is None:
        reasons.append("방문 이력이 없는 새로운 식당")
    elif last_days > exclude_recent:
        reasons.append(f"최근 {last_days}일간 방문하지 않음")
    try:
        if float(rest.get("avg_price", 0)) <= meal_budget:
            reasons.append("1회 예산 이내 가격")
    except (TypeError, ValueError):
        pass
    try:
        if float(rest.get("walk_minutes", 99)) <= 5:
            reasons.append("도보 5분 이내로 가까움")
    except (TypeError, ValueError):
        pass
    if rest.get("crowd_level") == "여유":
        reasons.append("혼잡도 낮음")
    if hint:
        cat = str(rest.get("category") or "")
        menu = f"{rest.get('main_menu') or ''} {rest.get('sub_menu') or ''}"
        for kw in hint.get("keywords", []):
            if kw and (kw in cat or kw in menu):
                reasons.append(f"요청한 '{kw}' 조건에 부합")
                break
    if not reasons:
        reasons.append("종합 점수가 높은 무난한 선택")
    return reasons


def recommend_lunch(today=None, settings=None, user_request=None,
                    party_size: int = 1, mode: str = None,
                    tag_filter=None, exclude_categories=None,
                    generate_comments: bool = True) -> dict:
    """
    오늘의 점심 식당을 1·2·3순위로 추천한다.
    반환: {
        "items": [추천 dict, ...],   # rank 1..N
        "relaxed": bool,             # 조건 완화 여부
        "relax_level": int,
        "message": str | None,       # 안내 문구
        "empty": bool,               # 식당 DB 비었거나 후보 0
    }
    """
    from services import settings as settings_service

    today = date_utils.to_date(today)
    if settings is None:
        settings = settings_service.get_all()

    top_n = settings.get("top_n", 3)
    meal_budget = settings.get("meal_budget", 12000)
    budget_mode = settings.get("budget_mode", "감점")

    all_rest = db.list_restaurants()
    if not all_rest:
        return {"items": [], "relaxed": False, "relax_level": 0, "empty": True,
                "message": "등록된 식당이 없습니다. 식당 DB를 먼저 등록하거나 샘플 데이터를 추가해주세요."}

    unavailable_ids = db.unavailable_restaurant_ids(today)
    last_visit_map = db.last_visited_date_map()
    count_map = db.visit_count_map()
    sat_map = db.avg_satisfaction_map()

    # 태그/자주만석 정보를 각 식당에 부착
    tmap = db.tags_map()
    ffull = db.frequent_full_ids()
    for r in all_rest:
        r["tags"] = tmap.get(r["id"], [])
        r["is_frequent_full"] = (r["id"] in ffull) or (r.get("status") == "자주 만석")

    # 자연어 요청 해석(AI 또는 규칙 기반) + 상황별 모드 힌트 병합
    hint = ai_analyzer.parse_natural_request(user_request, settings) if user_request else None
    hint = _merge_hints(hint, _hint_from_mode(mode))

    # 하드 필터 통과 후보
    base_candidates = [
        r for r in all_rest
        if _passes_hard_filters(r, today, settings.get("max_walk_minutes", 10), unavailable_ids)
    ]

    # 사용자 지정 필터(태그/제외 카테고리)는 완화 대상이 아니므로 먼저 적용한다
    if exclude_categories:
        excl = set(exclude_categories)
        base_candidates = [r for r in base_candidates if r.get("category") not in excl]
    if tag_filter:
        tf = set(tag_filter)
        base_candidates = [r for r in base_candidates if tf & set(r.get("tags") or [])]

    # 완화 단계: 0=기본, 1=카테고리해제, 2=최근방문완화, 3=도보15분, 4=동일, 5=예산제외해제
    relax_level = 0
    chosen = []
    while relax_level <= 5:
        chosen = _filter_and_score(
            base_candidates, settings, today, last_visit_map, count_map,
            meal_budget, budget_mode, hint, relax_level, unavailable_ids,
            party_size, sat_map,
        )
        if len(chosen) >= top_n:
            break
        relax_level += 1

    relaxed = relax_level > 0 and len(chosen) > 0

    if not chosen:
        return {"items": [], "relaxed": relaxed, "relax_level": relax_level, "empty": True,
                "message": "조건에 맞는 식당이 없습니다. 설정을 조정하거나 식당을 추가해주세요."}

    # 점수순 정렬 -> 카테고리 다양성 보정 후 상위 top_n (PRD 6.3)
    chosen.sort(key=lambda x: x["score"], reverse=True)
    items = _diversify(chosen, top_n)

    # 추천점수를 사람이 이해하는 '매칭도(%)'로 변환 (전체 후보 최고점 기준)
    max_score = max((c["score"] for c in chosen), default=1) or 1
    for i, item in enumerate(items, start=1):
        item["rank"] = i
        item["match"] = max(45, min(99, round(item["score"] / max_score * 100)))

    result = {
        "items": items,
        "relaxed": relaxed,
        "relax_level": relax_level,
        "empty": False,
        "message": "추천 후보가 부족하여 일부 조건을 완화했습니다." if relaxed else None,
    }

    # AI 코멘트 (실패해도 기본 결과 유지)
    if generate_comments:
        comments = ai_analyzer.generate_ai_recommendation_comments(items, settings, user_request)
        if comments:
            for item in items:
                item["ai_comment"] = comments.get(item["rank"])

    return result


def _diversify(sorted_items, top_n, tolerance=12.0):
    """
    점수순 정렬된 후보에서 1·2·3순위가 같은 카테고리에 몰리지 않도록 보정한다.
    각 슬롯에서 '최고점과 tolerance 이내' 후보 중 아직 안 쓴 카테고리를 우선 선택한다.
    """
    pool = list(sorted_items)
    picked = []
    used_categories = set()
    while pool and len(picked) < top_n:
        top_score = pool[0]["score"]
        # 최고점과 tolerance 이내인 후보들 중에서 고른다
        near_idx = [i for i, it in enumerate(pool) if top_score - it["score"] <= tolerance]
        # 아직 등장하지 않은 카테고리를 우선, 없으면 최고점
        choice = next((i for i in near_idx if pool[i].get("category") not in used_categories),
                      near_idx[0])
        it = pool.pop(choice)
        picked.append(it)
        used_categories.add(it.get("category"))
    return picked


def _filter_and_score(candidates, settings, today, last_visit_map, count_map,
                      meal_budget, budget_mode, hint, relax_level, unavailable_ids,
                      party_size=1, sat_map=None):
    """완화 단계에 따라 소프트 필터를 적용하고 점수를 매긴 후보 리스트를 반환한다."""
    exclude_recent = settings.get("exclude_recent_days", 5)
    exclude_category = settings.get("exclude_category_days", 2)
    max_walk = settings.get("max_walk_minutes", 10)

    # 완화 단계별 조정
    if relax_level >= 2:
        exclude_recent = max(1, exclude_recent // 2)  # 최근방문 제외 기간 완화
    if relax_level >= 3:
        max_walk = max(max_walk, 15)  # 도보 15분으로 확대

    apply_category_filter = relax_level < 1  # 1단계부터 카테고리 제외 해제

    recent_ids = db.recent_visited_restaurant_ids(exclude_recent, today)
    recent_cats = db.recent_visited_categories(exclude_category, today) if apply_category_filter else set()

    scored = []
    for r in candidates:
        # 인원수(단체) 조건: 2명 이상이면 단체 불가/수용인원 부족 식당 제외
        if party_size and party_size > 1:
            if not r.get("can_group"):
                continue
            try:
                cap = int(r.get("max_party") or 0)
            except (TypeError, ValueError):
                cap = 0
            if cap and party_size > cap:
                continue

        # 도보시간 초과
        try:
            if float(r.get("walk_minutes", 0)) > max_walk:
                continue
        except (TypeError, ValueError):
            pass
        # 최근 방문 제외
        if r["id"] in recent_ids:
            continue
        # 카테고리 중복 제외
        if apply_category_filter and r.get("category") in recent_cats:
            continue

        scored_result = _score_restaurant(
            r, settings, today, last_visit_map, count_map,
            meal_budget, budget_mode, hint, relax_level, sat_map,
        )
        if scored_result is None:
            continue
        score, reasons, breakdown = scored_result

        last_date = last_visit_map.get(r["id"])
        scored.append({
            "id": r["id"], "name": r["name"], "category": r.get("category"),
            "main_menu": r.get("main_menu"), "sub_menu": r.get("sub_menu"),
            "walk_minutes": r.get("walk_minutes"), "avg_price": r.get("avg_price"),
            "rating": r.get("rating"), "crowd_level": r.get("crowd_level"),
            "map_url": r.get("map_url"), "address": r.get("address"),
            "latitude": r.get("latitude"), "longitude": r.get("longitude"),
            "can_group": r.get("can_group"), "max_party": r.get("max_party"),
            "can_takeout": r.get("can_takeout"), "tags": r.get("tags") or [],
            "status": r.get("status"), "is_frequent_full": r.get("is_frequent_full"),
            "last_visited": last_date, "visit_count": count_map.get(r["id"], 0),
            "avg_satisfaction": (sat_map or {}).get(r["id"]),
            "score": score, "reasons": reasons, "breakdown": breakdown,
            "ai_comment": None,
        })
    return scored
