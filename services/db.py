"""
services/db.py
SQLite 데이터베이스 계층.
- DB 연결, 테이블 자동 생성(restaurants/visit_logs/unavailable_logs/settings/budgets)
- 식당 CRUD, 방문 기록 저장(save_visit), 방문 불가 저장(mark_unavailable_today)
- 최초 실행 시 data/mml.db가 없으면 자동 생성한다.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta

from utils import date_utils

# data/mml.db 경로 (프로젝트 루트 기준)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "mml.db")

# settings 테이블 기본값 (PRD 8.4)
DEFAULT_SETTINGS = {
    "exclude_recent_days": "5",
    "exclude_category_days": "2",
    "max_walk_minutes": "10",
    "top_n": "3",
    "random_weight": "10",
    "meal_budget": "12000",
    "monthly_budget": "250000",
    "budget_mode": "감점",
    "ai_enabled": "true",
    "ai_provider": "openai",
    "ai_model": "gpt-4o-mini",
    "ai_use_for_recommendation": "true",
    "ai_use_for_memo_analysis": "true",
    "ai_use_for_budget_advice": "true",
    # 점수 가중치 (설정 화면에서 수정 가능)
    "weight_preference": "1.0",
    "weight_distance": "1.0",
    "weight_price": "1.0",
    "weight_crowd": "1.0",
    "weight_budget": "1.0",
}


def get_connection() -> sqlite3.Connection:
    """DB 커넥션을 반환한다. data 디렉터리가 없으면 생성한다."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """필요한 테이블을 모두 생성하고 기본 설정값을 채운다(최초 실행 시 자동)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            main_menu TEXT,
            sub_menu TEXT,
            walk_minutes INTEGER DEFAULT 5,
            avg_price INTEGER DEFAULT 10000,
            rating REAL DEFAULT 3.0,
            crowd_level TEXT DEFAULT '보통',
            is_active INTEGER DEFAULT 1,
            is_blacklisted INTEGER DEFAULT 0,
            blacklist_until DATE,
            open_days TEXT DEFAULT '월,화,수,목,금',
            can_takeout INTEGER DEFAULT 0,
            can_group INTEGER DEFAULT 1,
            max_party INTEGER DEFAULT 0,
            address TEXT,
            latitude REAL,
            longitude REAL,
            memo TEXT,
            map_url TEXT,
            ai_summary TEXT,
            ai_tags TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS visit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER NOT NULL,
            visited_date DATE NOT NULL,
            visit_count INTEGER DEFAULT 1,
            satisfaction REAL,
            actual_price INTEGER,
            memo TEXT,
            ai_memo_summary TEXT,
            ai_sentiment TEXT,
            ai_tags TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id),
            UNIQUE (restaurant_id, visited_date)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS unavailable_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER NOT NULL,
            unavailable_date DATE NOT NULL,
            reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id),
            UNIQUE (restaurant_id, unavailable_date)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_month TEXT NOT NULL UNIQUE,
            monthly_budget INTEGER DEFAULT 250000,
            meal_budget INTEGER DEFAULT 12000,
            memo TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 기본 설정값이 없으면 채운다.
    for key, value in DEFAULT_SETTINGS.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
            (key, value),
        )

    # 기존 DB 마이그레이션: 누락된 컬럼을 추가한다.
    _migrate_restaurants(cur)

    conn.commit()
    conn.close()


def _migrate_restaurants(cur) -> None:
    """restaurants 테이블에 신규 컬럼(좌표/주소/수용인원)이 없으면 추가한다."""
    existing = {row["name"] for row in cur.execute("PRAGMA table_info(restaurants)").fetchall()}
    additions = {
        "max_party": "INTEGER DEFAULT 0",
        "address": "TEXT",
        "latitude": "REAL",
        "longitude": "REAL",
    }
    for col, ddl in additions.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE restaurants ADD COLUMN {col} {ddl};")


# ------------------------------------------------------------------
# 식당(restaurants) CRUD
# ------------------------------------------------------------------

_RESTAURANT_FIELDS = [
    "name", "category", "main_menu", "sub_menu", "walk_minutes", "avg_price",
    "rating", "crowd_level", "is_active", "is_blacklisted", "blacklist_until",
    "open_days", "can_takeout", "can_group", "max_party", "address",
    "latitude", "longitude", "memo", "map_url", "ai_summary", "ai_tags",
]


def list_restaurants(active_only: bool = False) -> list[dict]:
    """모든 식당 목록을 반환한다. active_only=True면 활성 식당만."""
    conn = get_connection()
    sql = "SELECT * FROM restaurants"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_restaurant(restaurant_id: int) -> dict | None:
    """식당 단건 조회."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_restaurant(data: dict) -> int:
    """
    식당을 추가하거나(이름 기준) 업데이트한다.
    동일한 식당명이 있으면 기존 데이터를 갱신한다(엑셀 업로드/수동 입력 공용).
    반환값: 식당 id.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 입력 데이터 정리: 정의된 필드만 사용
    payload = {k: data.get(k) for k in _RESTAURANT_FIELDS if k in data}

    existing = cur.execute(
        "SELECT id FROM restaurants WHERE name = ?", (payload.get("name"),)
    ).fetchone()

    if existing:
        rid = existing["id"]
        set_fields = [k for k in payload.keys() if k != "name"]
        if set_fields:
            assignments = ", ".join(f"{k} = ?" for k in set_fields)
            values = [payload[k] for k in set_fields]
            values.append(rid)
            cur.execute(
                f"UPDATE restaurants SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
    else:
        cols = list(payload.keys())
        placeholders = ", ".join("?" for _ in cols)
        cur.execute(
            f"INSERT INTO restaurants ({', '.join(cols)}) VALUES ({placeholders})",
            [payload[c] for c in cols],
        )
        rid = cur.lastrowid

    conn.commit()
    conn.close()
    return rid


def set_restaurant_active(restaurant_id: int, active: bool) -> None:
    """식당 활성/비활성 토글(삭제 대신 추천 제외)."""
    conn = get_connection()
    conn.execute(
        "UPDATE restaurants SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (1 if active else 0, restaurant_id),
    )
    conn.commit()
    conn.close()


def update_restaurant_ai(restaurant_id: int, ai_summary: str, ai_tags: str) -> None:
    """식당 상세보기용 AI 요약/태그를 저장한다."""
    conn = get_connection()
    conn.execute(
        "UPDATE restaurants SET ai_summary = ?, ai_tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (ai_summary, ai_tags, restaurant_id),
    )
    conn.commit()
    conn.close()


def count_restaurants() -> int:
    """등록된 식당 수."""
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) AS c FROM restaurants").fetchone()["c"]
    conn.close()
    return n


# ------------------------------------------------------------------
# 방문 기록(visit_logs)
# ------------------------------------------------------------------

def save_visit(restaurant_id, visited_date=None, satisfaction=None,
               actual_price=None, memo=None,
               ai_memo_summary=None, ai_sentiment=None, ai_tags=None) -> dict:
    """
    [여기로 방문] 클릭 시 방문 기록을 저장한다.
    - 같은 날짜 같은 식당은 중복 저장하지 않는다(UNIQUE).
    - actual_price 미입력 시 식당 평균가격을 기본값으로 저장한다.
    반환: {"ok": bool, "message": str}
    """
    visited_date = date_utils.to_date(visited_date).isoformat()

    # 실제 결제금액 미입력 시 평균가격 사용
    if actual_price in (None, "", 0):
        rest = get_restaurant(restaurant_id)
        actual_price = rest["avg_price"] if rest else None

    conn = get_connection()
    cur = conn.cursor()

    dup = cur.execute(
        "SELECT id FROM visit_logs WHERE restaurant_id = ? AND visited_date = ?",
        (restaurant_id, visited_date),
    ).fetchone()
    if dup:
        conn.close()
        return {"ok": False, "message": "이미 오늘 방문한 식당으로 저장되어 있습니다."}

    cur.execute(
        """
        INSERT INTO visit_logs
            (restaurant_id, visited_date, visit_count, satisfaction, actual_price,
             memo, ai_memo_summary, ai_sentiment, ai_tags)
        VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
        """,
        (restaurant_id, visited_date, satisfaction, actual_price, memo,
         ai_memo_summary, ai_sentiment, ai_tags),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "방문 기록이 저장되었습니다."}


def list_visit_logs(limit: int | None = None) -> list[dict]:
    """방문 기록을 식당명과 조인해 최신순으로 반환한다."""
    conn = get_connection()
    sql = """
        SELECT v.*, r.name AS restaurant_name, r.category AS category
        FROM visit_logs v
        JOIN restaurants r ON r.id = v.restaurant_id
        ORDER BY v.visited_date DESC, v.id DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_visit_log(visit_id: int) -> None:
    """방문 기록 삭제."""
    conn = get_connection()
    conn.execute("DELETE FROM visit_logs WHERE id = ?", (visit_id,))
    conn.commit()
    conn.close()


def recent_visited_restaurant_ids(within_days: int, today=None) -> set[int]:
    """최근 within_days일 이내 방문한 식당 id 집합."""
    today = date_utils.to_date(today)
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT restaurant_id, visited_date FROM visit_logs"
    ).fetchall()
    conn.close()
    result = set()
    for r in rows:
        if date_utils.days_between(today, r["visited_date"]) <= within_days:
            result.add(r["restaurant_id"])
    return result


def recent_visited_categories(within_days: int, today=None) -> set[str]:
    """최근 within_days일 이내 먹은 메뉴 카테고리 집합."""
    today = date_utils.to_date(today)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT r.category AS category, v.visited_date AS visited_date
        FROM visit_logs v JOIN restaurants r ON r.id = v.restaurant_id
        """
    ).fetchall()
    conn.close()
    result = set()
    for r in rows:
        if r["category"] and date_utils.days_between(today, r["visited_date"]) <= within_days:
            result.add(r["category"])
    return result


def last_visited_date_map() -> dict[int, str]:
    """식당별 가장 최근 방문일 매핑(restaurant_id -> 'YYYY-MM-DD')."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT restaurant_id, MAX(visited_date) AS last_date FROM visit_logs GROUP BY restaurant_id"
    ).fetchall()
    conn.close()
    return {r["restaurant_id"]: r["last_date"] for r in rows}


def visit_count_map() -> dict[int, int]:
    """식당별 누적 방문 횟수 매핑."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT restaurant_id, COUNT(*) AS cnt FROM visit_logs GROUP BY restaurant_id"
    ).fetchall()
    conn.close()
    return {r["restaurant_id"]: r["cnt"] for r in rows}


def avg_satisfaction_map() -> dict[int, float]:
    """식당별 평균 만족도 매핑(내가 남긴 만족도 기반, 추천 점수에 반영)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT restaurant_id, AVG(satisfaction) AS s FROM visit_logs "
        "WHERE satisfaction IS NOT NULL GROUP BY restaurant_id"
    ).fetchall()
    conn.close()
    return {r["restaurant_id"]: r["s"] for r in rows if r["s"] is not None}


def set_blacklist(restaurant_id: int, days: int = 30) -> None:
    """식당을 일정 기간 추천에서 제외(블랙리스트)한다. days<=0이면 해제."""
    conn = get_connection()
    if days and days > 0:
        until = (date_utils.today() + timedelta(days=days)).isoformat()
        conn.execute(
            "UPDATE restaurants SET is_blacklisted = 1, blacklist_until = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (until, restaurant_id),
        )
    else:
        conn.execute(
            "UPDATE restaurants SET is_blacklisted = 0, blacklist_until = NULL, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (restaurant_id,),
        )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# 방문 불가(unavailable_logs)
# ------------------------------------------------------------------

def mark_unavailable_today(restaurant_id, reason, unavailable_date=None) -> dict:
    """
    [방문 불가] 클릭 시 오늘 방문 불가 식당으로 저장한다.
    같은 날짜 중복은 사유를 갱신한다.
    """
    unavailable_date = date_utils.to_date(unavailable_date).isoformat()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO unavailable_logs (restaurant_id, unavailable_date, reason)
        VALUES (?, ?, ?)
        ON CONFLICT(restaurant_id, unavailable_date)
        DO UPDATE SET reason = excluded.reason
        """,
        (restaurant_id, unavailable_date, reason),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": "방문 불가로 처리되어 오늘 추천에서 제외됩니다."}


def unavailable_restaurant_ids(today=None) -> set[int]:
    """오늘 방문 불가 처리된 식당 id 집합."""
    today = date_utils.to_date(today).isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT restaurant_id FROM unavailable_logs WHERE unavailable_date = ?",
        (today,),
    ).fetchall()
    conn.close()
    return {r["restaurant_id"] for r in rows}


def clear_unavailable_today(today=None) -> None:
    """오늘 방문 불가 기록을 모두 초기화(추천 재계산용)."""
    today = date_utils.to_date(today).isoformat()
    conn = get_connection()
    conn.execute("DELETE FROM unavailable_logs WHERE unavailable_date = ?", (today,))
    conn.commit()
    conn.close()
