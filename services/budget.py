"""
services/budget.py
예산 계산 로직.
- 월별 예산 조회/저장(budgets 테이블)
- 이번 달 사용금액/남은 예산/사용률/평균 점심 비용 계산
- 예산 초과 여부 판정
"""

from __future__ import annotations

from services import db, settings as settings_service
from utils import date_utils


def get_or_create_budget(year_month: str) -> dict:
    """
    해당 월 예산을 조회한다. 없으면 settings 기본값으로 생성한다.
    """
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM budgets WHERE year_month = ?", (year_month,)
    ).fetchone()
    if row is None:
        monthly = settings_service.get("monthly_budget", 250000)
        meal = settings_service.get("meal_budget", 12000)
        conn.execute(
            "INSERT INTO budgets (year_month, monthly_budget, meal_budget) VALUES (?, ?, ?)",
            (year_month, monthly, meal),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM budgets WHERE year_month = ?", (year_month,)
        ).fetchone()
    conn.close()
    return dict(row)


def save_budget(year_month: str, monthly_budget: int, meal_budget: int, memo: str = None) -> None:
    """월 예산을 저장(upsert)한다."""
    conn = db.get_connection()
    conn.execute(
        """
        INSERT INTO budgets (year_month, monthly_budget, meal_budget, memo)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(year_month) DO UPDATE SET
            monthly_budget = excluded.monthly_budget,
            meal_budget = excluded.meal_budget,
            memo = excluded.memo,
            updated_at = CURRENT_TIMESTAMP
        """,
        (year_month, monthly_budget, meal_budget, memo),
    )
    conn.commit()
    conn.close()


def get_monthly_budget_status(year_month: str = None) -> dict:
    """
    월 예산, 현재 사용금액, 남은 예산, 사용률, 평균 점심 비용, 방문 횟수를 계산한다.
    """
    if year_month is None:
        year_month = date_utils.year_month()

    budget = get_or_create_budget(year_month)
    monthly_budget = budget["monthly_budget"]
    meal_budget = budget["meal_budget"]

    start, end = date_utils.month_range(year_month)
    conn = db.get_connection()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(actual_price), 0) AS spent,
               COUNT(*) AS cnt,
               AVG(actual_price) AS avg_price
        FROM visit_logs
        WHERE visited_date BETWEEN ? AND ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    conn.close()

    spent = int(row["spent"] or 0)
    cnt = int(row["cnt"] or 0)
    avg_price = round(row["avg_price"], 0) if row["avg_price"] else 0
    remaining = monthly_budget - spent
    usage_rate = round((spent / monthly_budget) * 100, 1) if monthly_budget > 0 else 0.0

    return {
        "year_month": year_month,
        "monthly_budget": monthly_budget,
        "meal_budget": meal_budget,
        "spent": spent,
        "remaining": remaining,
        "usage_rate": usage_rate,
        "avg_price": avg_price,
        "visit_count": cnt,
        "is_over": spent > monthly_budget,
        "remaining_workdays": date_utils.remaining_workdays(),
    }
