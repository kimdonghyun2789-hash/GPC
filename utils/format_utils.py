"""
utils/format_utils.py
표시용 포맷 유틸리티.
- 금액(원), 도보시간(분), 예산상태 라벨/색상, 퍼센트 등을 사람이 읽기 좋게 변환한다.
"""

from __future__ import annotations


def won(amount) -> str:
    """금액을 '9,000원' 형식으로 변환한다."""
    try:
        return f"{int(round(float(amount))):,}원"
    except (TypeError, ValueError):
        return "-"


def walk(minutes) -> str:
    """도보시간을 '도보 5분' 형식으로 변환한다."""
    try:
        return f"도보 {int(minutes)}분"
    except (TypeError, ValueError):
        return "도보 -"


def percent(value, digits: int = 1) -> str:
    """비율(0~100)을 '52.8%' 형식으로 변환한다."""
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return "-"


def rating(value) -> str:
    """선호도/만족도를 '★ 4.5' 형식으로 변환한다."""
    try:
        return f"★ {float(value):.1f}"
    except (TypeError, ValueError):
        return "★ -"


# 예산 상태 정의: (라벨, 색상, 이모지)
BUDGET_STATUS = {
    "ok": ("예산 적합", "#2e7d32", "🟢"),
    "near": ("예산 약간 초과", "#ef6c00", "🟠"),
    "over": ("예산 초과", "#c62828", "🔴"),
}


def budget_status_label(avg_price, meal_budget) -> str:
    """가격과 1회 예산을 비교해 예산 상태 키('ok'/'near'/'over')를 반환한다."""
    try:
        avg_price = float(avg_price)
        meal_budget = float(meal_budget)
    except (TypeError, ValueError):
        return "ok"
    if meal_budget <= 0:
        return "ok"
    if avg_price <= meal_budget:
        return "ok"
    if avg_price <= meal_budget * 1.2:
        return "near"
    return "over"


def budget_status_text(avg_price, meal_budget) -> str:
    """예산 상태를 '🟢 예산 적합' 형태의 텍스트로 반환한다."""
    key = budget_status_label(avg_price, meal_budget)
    label, _color, emoji = BUDGET_STATUS[key]
    return f"{emoji} {label}"


def truncate(text, length: int = 40) -> str:
    """긴 문자열을 잘라서 '...'을 붙인다."""
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= length else text[: length - 1] + "…"
