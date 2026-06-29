"""
services/settings.py
settings 테이블 읽기/쓰기 헬퍼.
- 문자열로 저장된 설정값을 적절한 타입(int/float/bool/str)으로 변환해 제공한다.
- get_all() 은 추천/예산/AI 로직에서 바로 쓰기 좋은 dict를 반환한다.
"""

from __future__ import annotations

from services import db

# 타입 캐스팅 규칙
_INT_KEYS = {
    "exclude_recent_days", "exclude_category_days", "max_walk_minutes",
    "top_n", "random_weight", "meal_budget", "monthly_budget",
}
_FLOAT_KEYS = {
    "weight_preference", "weight_distance", "weight_price",
    "weight_crowd", "weight_budget",
}
_BOOL_KEYS = {
    "ai_enabled", "ai_use_for_recommendation",
    "ai_use_for_memo_analysis", "ai_use_for_budget_advice",
}


def _cast(key: str, value):
    """저장된 문자열 값을 키에 맞는 타입으로 변환한다."""
    if value is None:
        return None
    if key in _BOOL_KEYS:
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    if key in _INT_KEYS:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if key in _FLOAT_KEYS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0
    return value


def get(key: str, default=None):
    """단일 설정값을 타입 변환해 반환한다."""
    conn = db.get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return default
    return _cast(key, row["value"])


def set(key: str, value) -> None:
    """단일 설정값을 저장한다(bool은 true/false 문자열로)."""
    if isinstance(value, bool):
        value = "true" if value else "false"
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def set_many(values: dict) -> None:
    """여러 설정값을 한 번에 저장한다."""
    for k, v in values.items():
        set(k, v)


def get_all() -> dict:
    """모든 설정값을 타입 변환된 dict로 반환한다."""
    conn = db.get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    result = {}
    for r in rows:
        result[r["key"]] = _cast(r["key"], r["value"])
    # 누락된 기본값 보강
    for k, v in db.DEFAULT_SETTINGS.items():
        if k not in result:
            result[k] = _cast(k, v)
    return result
