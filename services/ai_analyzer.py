"""
services/ai_analyzer.py
AI 기능의 실제 진입점(고수준 함수).
- 자연어 점심 요청 해석 -> 추천 가중치/필터 힌트
- 추천 코멘트 생성 (1·2·3순위)
- 방문 메모 분석 (요약/감정/태그/추천 영향)
- 식당별 누적 메모 요약
- 예산 조언 / 월별 리포트
모든 함수는 AI 미사용/실패 시에도 안전한 폴백 값을 반환한다.
"""

from __future__ import annotations

import json
import re

from services import ai_client, ai_prompts
from utils import format_utils


def parse_natural_request(user_request: str, settings: dict) -> dict:
    """
    자연어 점심 요청을 해석해 추천에 반영할 힌트 dict를 반환한다.
    형식: {
        "keywords": [...],          # 가중치 +가 될 카테고리/메뉴 키워드
        "prefer_short_walk": bool,  # 거리 가중
        "prefer_cheap": bool,       # 예산 가중
        "avoid_categories": [...],  # 회피 카테고리
        "raw": 원문
    }
    AI 미사용 시 키워드 기반 규칙으로 폴백한다.
    """
    hint = {
        "keywords": [],
        "prefer_short_walk": False,
        "prefer_cheap": False,
        "avoid_categories": [],
        "raw": user_request or "",
    }
    if not user_request:
        return hint

    text = user_request.strip()

    # --- 규칙 기반 기본 해석(AI 없어도 동작) ---
    rule_map = {
        "국물": ["한식", "국밥", "찌개", "라멘", "쌀국수"],
        "든든": ["한식", "백반", "돈까스"],
        "느끼": [],  # 회피 키워드는 아래에서 처리
        "가볍": ["샐러드", "분식"],
        "매콤": ["한식", "중식"],
    }
    for key, cats in rule_map.items():
        if key in text:
            hint["keywords"].extend(cats)

    if any(w in text for w in ["멀리", "가깝", "가까운", "근처", "빨리", "빠르"]):
        hint["prefer_short_walk"] = True
    if any(w in text for w in ["예산", "싼", "저렴", "안 넘", "안넘", "아끼"]):
        hint["prefer_cheap"] = True
    if "느끼" in text:
        hint["avoid_categories"].extend(["일식"])

    # --- AI 사용 가능하면 더 정교하게 보강 ---
    if ai_client.is_available(settings) and settings.get("ai_use_for_recommendation", True):
        system = "너는 점심 요청을 구조화 JSON으로만 변환하는 파서다. 설명 없이 JSON만 출력해라."
        prompt = (
            "다음 점심 요청을 분석해 아래 JSON 스키마로만 답해라.\n"
            f'요청: "{text}"\n'
            '스키마: {"keywords": ["카테고리나 메뉴 키워드"], '
            '"prefer_short_walk": true/false, "prefer_cheap": true/false, '
            '"avoid_categories": ["회피 카테고리"]}\n'
            "카테고리 예: 한식, 중식, 일식, 분식, 아시안, 샐러드"
        )
        raw = ai_client.chat(prompt, settings, system=system, temperature=0.2, max_tokens=300)
        parsed = _extract_json(raw)
        if isinstance(parsed, dict):
            if parsed.get("keywords"):
                hint["keywords"].extend([str(k) for k in parsed["keywords"]])
            if parsed.get("avoid_categories"):
                hint["avoid_categories"].extend([str(k) for k in parsed["avoid_categories"]])
            hint["prefer_short_walk"] = hint["prefer_short_walk"] or bool(parsed.get("prefer_short_walk"))
            hint["prefer_cheap"] = hint["prefer_cheap"] or bool(parsed.get("prefer_cheap"))

    # 중복 제거
    hint["keywords"] = list(dict.fromkeys(hint["keywords"]))
    hint["avoid_categories"] = list(dict.fromkeys(hint["avoid_categories"]))
    return hint


def generate_ai_recommendation_comments(recommendations: list[dict], settings: dict,
                                        user_request: str | None = None) -> dict | None:
    """
    추천 1·2·3순위에 대한 AI 코멘트를 생성한다.
    반환: {순위(int): 코멘트(str)} 또는 None(AI 미사용/실패).
    """
    if not recommendations:
        return None
    if not (ai_client.is_available(settings) and settings.get("ai_use_for_recommendation", True)):
        return None

    lines = []
    for r in recommendations:
        lines.append(
            f"{r['rank']}순위 {r['name']} / 분류:{r.get('category')} / "
            f"대표메뉴:{r.get('main_menu')} / 도보:{r.get('walk_minutes')}분 / "
            f"가격:{r.get('avg_price')}원 / 최근방문:{r.get('last_visited') or '없음'} / "
            f"점수:{r.get('score')}"
        )
    data = "\n".join(lines)
    if user_request:
        data += f"\n사용자 요청: {user_request}"

    prompt = ai_prompts.render("recommendation_comment", recommendation_data=data)
    system = "너는 회사 점심 추천 도우미다. 과장 없이 실용적으로 답해라."
    raw = ai_client.chat(prompt, settings, system=system, temperature=0.5, max_tokens=500)
    if not raw:
        return None

    # "1순위 코멘트: ..." 형태를 파싱
    comments = {}
    for rank in (1, 2, 3):
        m = re.search(rf"{rank}순위[^:：]*[:：]\s*(.+?)(?=\n\s*[1-3]순위|$)", raw, re.S)
        if m:
            comments[rank] = m.group(1).strip()
    if not comments:
        # 파싱 실패 시 전체 텍스트를 1순위에 부여
        comments[1] = raw.strip()
    return comments


def analyze_visit_memo_with_ai(restaurant_name, category, memo, satisfaction=None,
                               settings: dict | None = None) -> dict | None:
    """
    방문 메모를 AI로 분석해 요약/감정/태그/추천영향을 반환한다.
    반환: {"summary","sentiment","tags"(list),"recommendation_impact"} 또는 None.
    """
    settings = settings or {}
    if not memo:
        return None
    if not (ai_client.is_available(settings) and settings.get("ai_use_for_memo_analysis", True)):
        return None

    prompt = ai_prompts.render(
        "memo_analysis",
        restaurant_name=restaurant_name,
        category=category or "",
        memo=memo,
        satisfaction=satisfaction if satisfaction is not None else "",
    )
    system = "너는 방문 메모 분석기다. 설명 없이 JSON만 출력해라."
    raw = ai_client.chat(prompt, settings, system=system, temperature=0.2, max_tokens=300)
    parsed = _extract_json(raw)
    if not isinstance(parsed, dict):
        return None
    # tags가 리스트가 아니면 보정
    tags = parsed.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return {
        "summary": parsed.get("summary", ""),
        "sentiment": parsed.get("sentiment", "보통"),
        "tags": tags,
        "recommendation_impact": parsed.get("recommendation_impact", "유지"),
    }


def summarize_restaurant_memos(restaurant_name, category, memos: list[str],
                               settings: dict) -> dict | None:
    """식당 상세보기용: 누적 메모를 장단점/추천상황으로 요약한다."""
    if not memos:
        return None
    if not ai_client.is_available(settings):
        return None
    joined = "\n".join(f"- {m}" for m in memos if m)
    prompt = (
        f"식당명: {restaurant_name} (분류: {category})\n"
        f"누적 방문 메모:\n{joined}\n\n"
        "위 메모를 바탕으로 JSON으로만 답해라.\n"
        '{"summary": "한두 문장 요약", "pros": ["장점"], "cons": ["단점"], '
        '"good_for": ["추천 상황"], "tags": ["태그"]}'
    )
    system = "너는 식당 리뷰 요약기다. 설명 없이 JSON만 출력해라."
    raw = ai_client.chat(prompt, settings, system=system, temperature=0.3, max_tokens=400)
    parsed = _extract_json(raw)
    return parsed if isinstance(parsed, dict) else None


def generate_budget_advice(budget_status: dict, settings: dict) -> str | None:
    """예산 상태 dict를 받아 AI 조언 텍스트를 생성한다."""
    if not (ai_client.is_available(settings) and settings.get("ai_use_for_budget_advice", True)):
        return None
    prompt = ai_prompts.render(
        "budget_advice",
        monthly_budget=format_utils.won(budget_status.get("monthly_budget")),
        spent_amount=format_utils.won(budget_status.get("spent")),
        remaining_budget=format_utils.won(budget_status.get("remaining")),
        usage_rate=format_utils.percent(budget_status.get("usage_rate")),
        avg_lunch_price=format_utils.won(budget_status.get("avg_price")),
        remaining_workdays=budget_status.get("remaining_workdays", 0),
    )
    system = "너는 점심 예산 관리 도우미다. 간결하게 한국어로 답해라."
    return ai_client.chat(prompt, settings, system=system, temperature=0.4, max_tokens=400)


def generate_monthly_report(report_data: dict, settings: dict) -> str | None:
    """월별 점심 리포트를 생성한다."""
    if not ai_client.is_available(settings):
        return None
    data_text = json.dumps(report_data, ensure_ascii=False, indent=2)
    prompt = ai_prompts.render("monthly_report", report_data=data_text)
    system = "너는 점심 리포트 작성 도우미다. 자연스러운 한국어로 답해라."
    return ai_client.chat(prompt, settings, system=system, temperature=0.5, max_tokens=600)


def suggest_tags(restaurant: dict, memos: list[str], settings: dict) -> list[str] | None:
    """식당 정보 + 누적 메모로 AI가 태그를 추천한다(PRD Phase 5). 실패 시 None."""
    if not ai_client.is_available(settings):
        return None
    memo_text = " / ".join(m for m in (memos or []) if m) or "(메모 없음)"
    prompt = (
        f"식당명: {restaurant.get('name')}\n분류: {restaurant.get('category')}\n"
        f"대표메뉴: {restaurant.get('main_menu')}\n평균가격(1인): {restaurant.get('avg_price')}\n"
        f"방문 메모: {memo_text}\n\n"
        "이 식당에 어울리는 짧은 태그 3~6개를 JSON 배열로만 답해라. "
        '예: ["가성비","국물","빠른 점심"]'
    )
    system = "너는 식당 태그를 다는 도우미다. 설명 없이 JSON 배열만 출력해라."
    raw = ai_client.chat(prompt, settings, system=system, temperature=0.3, max_tokens=120)
    parsed = _extract_json_array(raw)
    return parsed


def daily_oneliner(items: list[dict], settings: dict) -> str | None:
    """오늘의 추천 묶음에 대한 친근한 한 줄 코멘트(PRD Phase 5)."""
    if not items:
        return None
    names = ", ".join(f"{it['rank']}.{it['name']}" for it in items)
    if not ai_client.is_available(settings):
        # 비-AI 폴백: 1순위 기반 템플릿
        top = items[0]
        return f"오늘은 {top['name']} 어때요? 1·2·3순위로 골라뒀어요."
    prompt = (
        f"오늘 점심 추천 후보: {names}\n"
        "이 추천을 소개하는 친근한 한 줄 코멘트를 한국어로 1문장만 작성해라. 이모지 1개 이내."
    )
    system = "너는 친근한 점심 도우미다. 한 문장으로만 답해라."
    raw = ai_client.chat(prompt, settings, system=system, temperature=0.7, max_tokens=80)
    return raw.strip() if raw else None


def analyze_taste(taste_data: dict, settings: dict) -> str | None:
    """방문 이력 기반 개인 취향 분석 리포트(PRD Phase 5). AI 없으면 None."""
    if not ai_client.is_available(settings):
        return None
    data_text = json.dumps(taste_data, ensure_ascii=False)
    prompt = (
        "아래는 한 사용자의 점심 방문 데이터다. 이 사람의 점심 취향을 3~4문장으로 "
        "분석하고, 다음에 시도하면 좋을 메뉴를 제안해라.\n" + data_text
    )
    system = "너는 식습관 분석 도우미다. 자연스러운 한국어로 답해라."
    return ai_client.chat(prompt, settings, system=system, temperature=0.5, max_tokens=400)


def _extract_json_array(raw: str | None):
    """문자열에서 JSON 배열을 추출한다(태그 추천용)."""
    if not raw:
        return None
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\[.*\]", cleaned, re.S)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
        return [str(x).strip() for x in arr if str(x).strip()]
    except json.JSONDecodeError:
        return None


def _extract_json(raw: str | None):
    """문자열에서 첫 번째 JSON 객체를 추출해 파싱한다(코드블록/잡음 허용)."""
    if not raw:
        return None
    # ```json ... ``` 코드블록 제거
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
