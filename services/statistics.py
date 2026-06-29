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


def spending_by_category(year_month: str = None) -> list[dict]:
    """이번 달 카테고리별 지출 합계(PRD 7.4)."""
    if year_month is None:
        year_month = date_utils.year_month()
    start, end = date_utils.month_range(year_month)
    conn = db.get_connection()
    rows = conn.execute(
        """
        SELECT COALESCE(r.category, '기타') AS category,
               COALESCE(SUM(v.actual_price), 0) AS total,
               COUNT(*) AS cnt
        FROM visit_logs v JOIN restaurants r ON r.id = v.restaurant_id
        WHERE v.visited_date BETWEEN ? AND ?
        GROUP BY r.category ORDER BY total DESC
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def expensive_restaurants(year_month: str = None, limit: int = 5) -> list[dict]:
    """이번 달 평균 결제금액이 높은 식당 TOP N(PRD 7.4)."""
    if year_month is None:
        year_month = date_utils.year_month()
    start, end = date_utils.month_range(year_month)
    conn = db.get_connection()
    rows = conn.execute(
        """
        SELECT r.name AS name, ROUND(AVG(v.actual_price)) AS avg_paid, COUNT(*) AS cnt
        FROM visit_logs v JOIN restaurants r ON r.id = v.restaurant_id
        WHERE v.visited_date BETWEEN ? AND ? AND v.actual_price IS NOT NULL
        GROUP BY v.restaurant_id ORDER BY avg_paid DESC LIMIT ?
        """,
        (start.isoformat(), end.isoformat(), limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def value_restaurants(limit: int = 5) -> list[dict]:
    """가성비 식당 TOP N: 만족도가 있으면서 (만족도 대비 가격)이 좋은 순(PRD 7.4)."""
    conn = db.get_connection()
    rows = conn.execute(
        """
        SELECT r.name AS name, r.avg_price AS price,
               ROUND(AVG(v.satisfaction), 1) AS satisfaction, COUNT(*) AS cnt
        FROM visit_logs v JOIN restaurants r ON r.id = v.restaurant_id
        WHERE v.satisfaction IS NOT NULL
        GROUP BY v.restaurant_id
        """
    ).fetchall()
    conn.close()
    # 가성비 점수 = 만족도 / (가격/10000)  -> 높을수록 가성비 좋음
    items = []
    for r in rows:
        price = r["price"] or 1
        score = (r["satisfaction"] or 0) / (price / 10000.0) if price else 0
        items.append({**dict(r), "value_score": round(score, 2)})
    items.sort(key=lambda x: x["value_score"], reverse=True)
    return items[:limit]


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
