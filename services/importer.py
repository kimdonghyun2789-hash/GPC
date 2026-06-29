"""
services/importer.py
엑셀 업로드 및 샘플 데이터 처리.
- 한글 컬럼명 -> DB 필드 매핑
- 동일 식당명은 업데이트(upsert)
- 샘플 식당 10곳 일괄 추가
"""

from __future__ import annotations

import io

import pandas as pd

from services import db, naver_map
from utils import date_utils

# 네이버 지역 검색에 사용할 기본 키워드 (PRD 3.1)
NAVER_SEARCH_KEYWORDS = [
    "한식", "중식", "일식", "양식", "분식",
    "국밥", "돈까스", "냉면", "샐러드", "백반",
]

# 네이버 카테고리 문자열 -> 앱 내부 분류 매핑
_CATEGORY_BUCKETS = {
    "한식": "한식", "국밥": "한식", "백반": "한식", "냉면": "한식", "찌개": "한식",
    "중식": "중식", "일식": "일식", "돈까스": "일식", "라멘": "일식", "초밥": "일식",
    "양식": "양식", "이탈리아": "양식", "파스타": "양식",
    "분식": "분식", "샐러드": "샐러드", "아시아": "아시안", "베트남": "아시안",
    "카페": "카페", "디저트": "카페",
}


def _bucket_category(naver_category: str, fallback: str) -> str:
    """네이버 카테고리 문자열을 앱 내부 분류로 단순화한다."""
    text = naver_category or ""
    for key, bucket in _CATEGORY_BUCKETS.items():
        if key in text:
            return bucket
    return fallback


def import_from_naver(base_location: str, keywords=None, display: int = 5) -> dict:
    """
    네이버 지역 검색으로 기준 위치 주변 식당을 수집해 DB에 upsert한다(PRD 3.1).
    동일 식당명은 기존 데이터를 업데이트(병합)한다.
    반환: {"ok","saved","by_keyword","queries","message"}
    """
    if not naver_map.is_search_available():
        return {"ok": False, "saved": 0, "by_keyword": {}, "queries": 0,
                "message": "네이버 지역 검색 키(NAVER_SEARCH_CLIENT_ID/SECRET)가 없습니다."}
    if not base_location:
        return {"ok": False, "saved": 0, "by_keyword": {}, "queries": 0,
                "message": "기준 위치(회사 주소 또는 지역명)를 입력해주세요."}

    keywords = keywords or NAVER_SEARCH_KEYWORDS
    by_keyword: dict[str, int] = {}
    seen_names: set[str] = set()
    total_saved = 0
    queries = 0

    for kw in keywords:
        query = f"{base_location} {kw}"
        items = naver_map.search_local(query, display=display)
        queries += 1
        saved_for_kw = 0
        for it in items:
            name = it.get("name")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            db.upsert_restaurant({
                "name": name,
                "category": _bucket_category(it.get("category"), kw),
                "address": it.get("road_address") or it.get("address"),
                "latitude": it.get("lat"),
                "longitude": it.get("lng"),
                "map_url": it.get("link"),
            })
            saved_for_kw += 1
            total_saved += 1
        by_keyword[kw] = saved_for_kw
        db.log_api_sync("local_search", query, len(items), True)

    return {"ok": True, "saved": total_saved, "by_keyword": by_keyword,
            "queries": queries,
            "message": f"네이버에서 {total_saved}곳을 수집/갱신했습니다."}


def recompute_walk_minutes(base_location: str) -> dict:
    """
    기준 위치를 좌표로 변환한 뒤, 좌표가 있는 식당의 도보시간을 직선거리 기반으로 자동 계산한다.
    네이버 지도(NCP) 키가 필요하다(기준 위치 geocoding).
    반환: {"ok","updated","message"}
    """
    if not naver_map.is_available():
        return {"ok": False, "updated": 0,
                "message": "네이버 지도 키(NAVER_MAP_CLIENT_ID/SECRET)가 필요합니다."}
    geo = naver_map.geocode(base_location)
    if not geo:
        return {"ok": False, "updated": 0, "message": "기준 위치 좌표를 찾지 못했습니다."}

    base_lat, base_lng = geo["lat"], geo["lng"]
    updated = 0
    for r in db.list_restaurants():
        if r.get("latitude") and r.get("longitude"):
            mins = naver_map.estimate_walk_minutes(base_lat, base_lng, r["latitude"], r["longitude"])
            if mins:
                db.upsert_restaurant({"name": r["name"], "walk_minutes": mins})
                updated += 1
    return {"ok": True, "updated": updated,
            "message": f"{updated}곳의 도보시간을 좌표 기반으로 자동 계산했습니다."}

# 엑셀 한글 컬럼 -> DB 필드 매핑
_COLUMN_MAP = {
    "식당명": "name",
    "메뉴분류": "category",
    "대표메뉴": "main_menu",
    "보조메뉴": "sub_menu",
    "도보시간": "walk_minutes",
    "평균가격": "avg_price",
    "선호도": "rating",
    "혼잡도": "crowd_level",
    "영업요일": "open_days",
    "포장가능": "can_takeout",
    "단체가능": "can_group",
    "수용인원": "max_party",
    "주소": "address",
    "위도": "latitude",
    "경도": "longitude",
    "메모": "memo",
    "지도URL": "map_url",
}

REQUIRED_COLUMNS = ["식당명", "메뉴분류", "대표메뉴", "도보시간", "평균가격"]


def _to_bool_int(value) -> int:
    """'예/Y/1/True' 등을 1, 그 외를 0으로 변환한다."""
    if value is None:
        return 0
    s = str(value).strip().lower()
    return 1 if s in ("1", "y", "yes", "예", "o", "true", "가능", "t") else 0


def import_from_dataframe(df: pd.DataFrame) -> dict:
    """
    DataFrame을 받아 식당 DB에 upsert한다.
    반환: {"ok": bool, "inserted": n, "message": str}
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return {"ok": False, "inserted": 0,
                "message": f"필수 컬럼이 없습니다: {', '.join(missing)}"}

    count = 0
    for _, row in df.iterrows():
        data = {}
        for kor, field in _COLUMN_MAP.items():
            if kor not in df.columns:
                continue
            value = row[kor]
            if pd.isna(value):
                value = None
            if field in ("can_takeout", "can_group"):
                value = _to_bool_int(value)
            elif field in ("walk_minutes", "avg_price", "max_party"):
                try:
                    value = int(float(value)) if value is not None else None
                except (TypeError, ValueError):
                    value = None
            elif field in ("rating", "latitude", "longitude"):
                try:
                    value = float(value) if value is not None else None
                except (TypeError, ValueError):
                    value = None
            data[field] = value

        if not data.get("name"):
            continue
        db.upsert_restaurant(data)
        count += 1

    return {"ok": True, "inserted": count, "message": f"{count}개 식당을 반영했습니다."}


def import_from_excel(file) -> dict:
    """업로드된 엑셀 파일(파일 객체/경로)을 읽어 import한다."""
    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "inserted": 0, "message": f"엑셀을 읽지 못했습니다: {e}"}
    return import_from_dataframe(df)


def _parse_pasted(text: str) -> pd.DataFrame:
    """엑셀/시트에서 복사한 텍스트(탭/콤마 구분)를 DataFrame으로 파싱한다."""
    # sep=None + engine='python' 이면 구분자(탭/콤마)를 자동 추론한다.
    return pd.read_csv(io.StringIO(text.strip()), sep=None, engine="python")


def import_from_pasted_text(text: str) -> dict:
    """엑셀/구글시트에서 복사해 붙여넣은 식당 표를 import한다(첫 줄=헤더)."""
    if not text or not text.strip():
        return {"ok": False, "inserted": 0, "message": "붙여넣은 내용이 없습니다."}
    try:
        df = _parse_pasted(text)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "inserted": 0, "message": f"표를 인식하지 못했습니다: {e}"}
    return import_from_dataframe(df)


# 방문 기록 붙여넣기용 컬럼 매핑
_VISIT_COLMAP = {
    "식당명": "name", "방문일": "date", "날짜": "date",
    "금액": "price", "실제결제금액": "price", "결제금액": "price",
    "만족도": "satisfaction", "별점": "satisfaction", "메모": "memo",
}


def import_visits_from_dataframe(df: pd.DataFrame) -> dict:
    """
    방문 기록 표를 import한다. 필수 컬럼: 식당명, 방문일.
    식당이 없으면 이름만으로 자동 생성한 뒤 방문을 저장한다.
    """
    cols = {c: _VISIT_COLMAP[c] for c in df.columns if c in _VISIT_COLMAP}
    if "name" not in cols.values() or "date" not in cols.values():
        return {"ok": False, "inserted": 0,
                "message": "필수 컬럼이 없습니다: 식당명, 방문일"}

    name_to_id = {r["name"]: r["id"] for r in db.list_restaurants()}
    saved = dup = created = 0
    for _, row in df.iterrows():
        rec = {field: row[col] for col, field in cols.items()}
        name = str(rec.get("name") or "").strip()
        if not name or pd.isna(rec.get("date")):
            continue
        rid = name_to_id.get(name)
        if rid is None:  # 없는 식당은 이름만으로 생성
            rid = db.upsert_restaurant({"name": name})
            name_to_id[name] = rid
            created += 1
        price = rec.get("price")
        sat = rec.get("satisfaction")
        memo = rec.get("memo")
        result = db.save_visit(
            restaurant_id=rid,
            visited_date=date_utils.to_date(rec["date"]),
            satisfaction=float(sat) if sat is not None and not pd.isna(sat) else None,
            actual_price=int(float(price)) if price is not None and not pd.isna(price) else None,
            memo=str(memo) if memo is not None and not pd.isna(memo) else None,
        )
        if result["ok"]:
            saved += 1
        else:
            dup += 1

    msg = f"방문 기록 {saved}건 저장"
    if created:
        msg += f" · 신규 식당 {created}곳 생성"
    if dup:
        msg += f" · 중복 {dup}건 건너뜀"
    return {"ok": True, "inserted": saved, "message": msg}


def import_visits_from_text(text: str) -> dict:
    """붙여넣은 방문 기록 표를 import한다."""
    if not text or not text.strip():
        return {"ok": False, "inserted": 0, "message": "붙여넣은 내용이 없습니다."}
    try:
        df = _parse_pasted(text)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "inserted": 0, "message": f"표를 인식하지 못했습니다: {e}"}
    return import_visits_from_dataframe(df)


# PRD 22. 샘플 데이터
SAMPLE_RESTAURANTS = [
    {"name": "김치찌개집", "category": "한식", "main_menu": "김치찌개, 제육", "walk_minutes": 5, "avg_price": 9000, "rating": 4.3, "crowd_level": "보통"},
    {"name": "돈까스집", "category": "일식", "main_menu": "등심돈까스, 카츠동", "walk_minutes": 7, "avg_price": 11000, "rating": 4.0, "crowd_level": "보통"},
    {"name": "쌀국수집", "category": "아시안", "main_menu": "쌀국수, 볶음밥", "walk_minutes": 6, "avg_price": 10000, "rating": 3.9, "crowd_level": "여유"},
    {"name": "중국집", "category": "중식", "main_menu": "짜장면, 짬뽕", "walk_minutes": 4, "avg_price": 9000, "rating": 3.8, "crowd_level": "혼잡"},
    {"name": "국밥집", "category": "한식", "main_menu": "돼지국밥", "walk_minutes": 8, "avg_price": 10000, "rating": 4.1, "crowd_level": "보통"},
    {"name": "냉면집", "category": "한식", "main_menu": "냉면, 만두", "walk_minutes": 9, "avg_price": 11000, "rating": 3.7, "crowd_level": "여유"},
    {"name": "분식집", "category": "분식", "main_menu": "김밥, 라면", "walk_minutes": 3, "avg_price": 7000, "rating": 3.6, "crowd_level": "보통"},
    {"name": "샐러드집", "category": "샐러드", "main_menu": "샐러드볼", "walk_minutes": 6, "avg_price": 12000, "rating": 3.9, "crowd_level": "여유"},
    {"name": "라멘집", "category": "일식", "main_menu": "라멘", "walk_minutes": 10, "avg_price": 12000, "rating": 4.2, "crowd_level": "혼잡"},
    {"name": "백반집", "category": "한식", "main_menu": "백반", "walk_minutes": 5, "avg_price": 9000, "rating": 4.0, "crowd_level": "보통"},
]


def add_sample_data() -> int:
    """샘플 식당 데이터를 추가(upsert)한다. 반환: 반영 개수."""
    for s in SAMPLE_RESTAURANTS:
        db.upsert_restaurant(s)
    return len(SAMPLE_RESTAURANTS)
