"""
services/importer.py
엑셀 업로드 및 샘플 데이터 처리.
- 한글 컬럼명 -> DB 필드 매핑
- 동일 식당명은 업데이트(upsert)
- 샘플 식당 10곳 일괄 추가
"""

from __future__ import annotations

import pandas as pd

from services import db

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
