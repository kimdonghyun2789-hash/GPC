"""
services/statistics.py
방문 기록 기반 통계 집계.
- 식당별/카테고리별 방문 횟수, 월별 식비 합계, 평균 비용, 만족도 평균
- 월별 리포트용 데이터 묶음 생성
"""

from __future__ import annotations

from services import db
from utils import date_utils


def visits_by_restaurant() -> list[dict]:
    """식당별 방문 횟수/평균 만족도/총 지출."""
    conn = db.get_connection()
    rows = conn.execute(
        """
        SELECT r.name AS name, COUNT(*) AS visits,
               AVG(v.satisfaction) AS avg_satisfaction,
               COALESCE(SUM(v.actual_price), 0) AS total_spent
        FROM visit_logs v JOIN restaurants r ON r.id = v.restaurant_id
        GROUP BY v.restaurant_id
        ORDER BY visits DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def visits_by_category() -> list[dict]:
    """카테고리별 방문 횟수."""
    conn = db.get_connection()
    rows = conn.execute(
        """
        SELECT COALESCE(r.category, '기타') AS category, COUNT(*) AS visits
        FROM visit_logs v JOIN restaurants r ON r.id = v.restaurant_id
        GROUP BY r.category
        ORDER BY visits DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def monthly_spending(year_month: str = None) -> dict:
    """해당 월의 식비 합계/평균/만족도 평균/방문 수."""
    if year_month is None:
        year_month = date_utils.year_month()
    start, end = date_utils.month_range(year_month)
    conn = db.get_connection()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(actual_price), 0) AS total,
               AVG(actual_price) AS avg_price,
               AVG(satisfaction) AS avg_satisfaction,
               COUNT(*) AS cnt
        FROM visit_logs
        WHERE visited_date BETWEEN ? AND ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    conn.close()
    return {
        "year_month": year_month,
        "total": int(row["total"] or 0),
        "avg_price": round(row["avg_price"], 0) if row["avg_price"] else 0,
        "avg_satisfaction": round(row["avg_satisfaction"], 2) if row["avg_satisfaction"] else None,
        "count": int(row["cnt"] or 0),
    }


def build_monthly_report_data(year_month: str = None) -> dict:
    """월별 AI 리포트 생성을 위한 데이터 묶음."""
    if year_month is None:
        year_month = date_utils.year_month()
    spending = monthly_spending(year_month)
    by_cat = visits_by_category()
    by_rest = visits_by_restaurant()
    top_satisfaction = sorted(
        [r for r in by_rest if r["avg_satisfaction"] is not None],
        key=lambda x: x["avg_satisfaction"], reverse=True,
    )[:3]
    return {
        "year_month": year_month,
        "total_visits": spending["count"],
        "total_spent": spending["total"],
        "avg_price": spending["avg_price"],
        "avg_satisfaction": spending["avg_satisfaction"],
        "by_category": by_cat,
        "top_restaurants_by_satisfaction": [r["name"] for r in top_satisfaction],
    }
