"""
utils/score_utils.py
추천 점수 계산에 사용하는 순수 함수 모음.
- 각 항목별 점수(선호도/거리/가격/혼잡도/예산/방문횟수/최근미방문)를 계산한다.
- recommender.py에서 가중치와 함께 조합해 최종 점수를 만든다.
- DB나 Streamlit에 의존하지 않는 순수 로직이라 단독 테스트가 쉽다.
"""

from __future__ import annotations

# 혼잡도 문자열 -> 점수 (덜 혼잡할수록 가점)
_CROWD_SCORE = {
    "여유": 10.0,
    "보통": 5.0,
    "혼잡": 0.0,
    "매우혼잡": -5.0,
}


def preference_score(rating) -> float:
    """선호도(0~5)를 0~10 점수로 환산한다."""
    try:
        return max(0.0, min(5.0, float(rating))) * 2.0
    except (TypeError, ValueError):
        return 6.0


def distance_score(walk_minutes, max_walk_minutes) -> float:
    """
    도보시간이 짧을수록 높은 점수.
    최대 도보시간 대비 비율로 0~10 점수를 만든다.
    """
    try:
        walk_minutes = float(walk_minutes)
        max_walk_minutes = float(max_walk_minutes)
    except (TypeError, ValueError):
        return 5.0
    if max_walk_minutes <= 0:
        return 5.0
    ratio = min(1.0, walk_minutes / max_walk_minutes)
    return round((1.0 - ratio) * 10.0, 2)


def price_score(avg_price, meal_budget) -> float:
    """
    가격이 1회 예산 대비 쌀수록 높은 점수.
    """
    try:
        avg_price = float(avg_price)
        meal_budget = float(meal_budget)
    except (TypeError, ValueError):
        return 5.0
    if meal_budget <= 0:
        return 5.0
    ratio = avg_price / meal_budget
    if ratio <= 0.7:
        return 10.0
    if ratio <= 1.0:
        return 7.0
    if ratio <= 1.2:
        return 3.0
    return 0.0


def crowd_score(crowd_level) -> float:
    """혼잡도 문자열을 점수로 변환한다."""
    return _CROWD_SCORE.get(str(crowd_level).strip(), 5.0)


def recency_score(last_visited_days, exclude_recent_days) -> float:
    """
    최근 방문일로부터 오래될수록 가점.
    last_visited_days가 None이면(방문 이력 없음) 최대 가점.
    """
    if last_visited_days is None:
        return 10.0
    try:
        last_visited_days = float(last_visited_days)
        exclude_recent_days = float(exclude_recent_days)
    except (TypeError, ValueError):
        return 5.0
    base = max(exclude_recent_days, 1.0)
    return round(min(1.0, last_visited_days / (base * 2)) * 10.0, 2)


def visit_count_score(visit_count) -> float:
    """
    누적 방문 횟수가 적을수록 가점(같은 곳만 가는 것을 방지).
    """
    try:
        visit_count = int(visit_count)
    except (TypeError, ValueError):
        visit_count = 0
    if visit_count <= 0:
        return 10.0
    if visit_count <= 2:
        return 6.0
    if visit_count <= 5:
        return 3.0
    return 0.0


def budget_score(avg_price, meal_budget, budget_mode) -> float | None:
    """
    PRD 12.6 예산 점수 규칙.
    budget_mode가 '제외'이고 예산 초과면 None을 반환(후보에서 제외 신호).
    """
    try:
        avg_price = float(avg_price)
        meal_budget = float(meal_budget)
    except (TypeError, ValueError):
        return 0.0
    if budget_mode == "제외" and avg_price > meal_budget:
        return None
    if avg_price <= meal_budget:
        return 10.0
    if avg_price <= meal_budget * 1.2:
        return 3.0
    # 감점 모드 또는 추천 가능 모드
    if budget_mode == "감점":
        return -10.0
    return -3.0
