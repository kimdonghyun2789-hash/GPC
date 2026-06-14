# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - SQLite 데이터베이스 모듈."""
import json
import sqlite3
from datetime import datetime
from typing import Optional

from utils import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    keywords TEXT,
    exclude_keywords TEXT,
    idea_dna_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS patents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_no TEXT UNIQUE,
    publication_no TEXT,
    registration_no TEXT,
    title TEXT,
    applicant TEXT,
    application_date TEXT,
    publication_date TEXT,
    registration_date TEXT,
    status TEXT,
    abstract TEXT,
    representative_claim TEXT,
    ipc TEXT,
    cpc TEXT,
    drawing_url TEXT,
    kipris_url TEXT,
    raw_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS search_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER,
    patent_id INTEGER,
    search_query TEXT,
    vector_score REAL,
    keyword_score REAL,
    dna_score REAL,
    claim_score REAL,
    ipc_score REAL,
    ai_risk_score REAL,
    total_score REAL,
    matched_keywords TEXT,
    technology_group TEXT,
    patent_dna_json TEXT,
    created_at TEXT,
    FOREIGN KEY (idea_id) REFERENCES ideas(id),
    FOREIGN KEY (patent_id) REFERENCES patents(id)
);

CREATE TABLE IF NOT EXISTS drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patent_id INTEGER,
    image_path TEXT,
    caption TEXT,
    created_at TEXT,
    FOREIGN KEY (patent_id) REFERENCES patents(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS review_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER,
    title TEXT,
    description TEXT,
    keywords TEXT,
    scope TEXT,
    top_n INTEGER,
    status TEXT,
    final_verdict TEXT,
    confidence TEXT,
    n_results INTEGER,
    high_risk INTEGER,
    snapshot_json TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (idea_id) REFERENCES ideas(id)
);

CREATE TABLE IF NOT EXISTS monitoring_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    keywords TEXT,
    ipc TEXT,
    applicant TEXT,
    scope TEXT,
    enabled INTEGER DEFAULT 1,
    last_run_at TEXT,
    created_at TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db() -> None:
    """데이터베이스 초기화 (settings 는 유지)."""
    conn = get_connection()
    try:
        for table in ("search_results", "drawings", "patents", "ideas",
                      "review_cases"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- settings
def get_setting(key: str) -> Optional[str]:
    try:
        conn = get_connection()
        try:
            conn.executescript(SCHEMA)
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------- ideas
def save_idea(title: str, description: str, keywords: str,
              exclude_keywords: str, idea_dna: dict) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO ideas(title, description, keywords, exclude_keywords,"
            " idea_dna_json, created_at) VALUES(?,?,?,?,?,?)",
            (title, description, keywords, exclude_keywords,
             json.dumps(idea_dna or {}, ensure_ascii=False),
             datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ----------------------------------------------------------------- patents
def upsert_patent(p: dict) -> int:
    """출원번호 기준으로 특허를 저장(중복 시 기존 id 반환)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM patents WHERE application_no = ?",
            (p.get("application_no"),),
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO patents(application_no, publication_no,"
            " registration_no, title, applicant, application_date,"
            " publication_date, registration_date, status, abstract,"
            " representative_claim, ipc, cpc, drawing_url, kipris_url,"
            " raw_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (p.get("application_no"), p.get("publication_no"),
             p.get("registration_no"), p.get("title"), p.get("applicant"),
             p.get("application_date"), p.get("publication_date"),
             p.get("registration_date"), p.get("status"), p.get("abstract"),
             p.get("representative_claim"), p.get("ipc"), p.get("cpc"),
             p.get("drawing_url"), p.get("kipris_url"),
             json.dumps(p, ensure_ascii=False, default=str),
             datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def save_search_result(idea_id: int, patent_id: int, scores: dict) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO search_results(idea_id, patent_id, search_query,"
            " vector_score, keyword_score, dna_score, claim_score, ipc_score,"
            " ai_risk_score, total_score, matched_keywords, technology_group,"
            " patent_dna_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (idea_id, patent_id, scores.get("search_query", ""),
             scores.get("vector_score", 0), scores.get("keyword_score", 0),
             scores.get("dna_score", 0), scores.get("claim_score", 0),
             scores.get("ipc_score", 0), scores.get("ai_risk_score", 0),
             scores.get("total_score", 0),
             json.dumps(scores.get("matched_keywords", []), ensure_ascii=False),
             scores.get("technology_group", "기타"),
             json.dumps(scores.get("patent_dna", {}), ensure_ascii=False),
             datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


BOOKMARK_SCHEMA = """
CREATE TABLE IF NOT EXISTS bookmarks (
    application_no TEXT PRIMARY KEY,
    title TEXT,
    applicant TEXT,
    note TEXT,
    created_at TEXT
);
"""


# 검토 상태 7종 (한글 UI / 내부 enum). 관심특허·검토케이스 공통 사용.
REVIEW_STATUSES = ["초안", "검토중", "보완필요", "출원후보",
                   "변리사검토", "보류", "제외"]
STATUS_ENUM = {
    "초안": "DRAFT", "검토중": "REVIEWING", "보완필요": "NEED_REVISION",
    "출원후보": "PATENT_CANDIDATE", "변리사검토": "ATTORNEY_REVIEW",
    "보류": "HOLD", "제외": "EXCLUDED",
}
# 구버전 상태값 → 신버전 매핑 (기존 DB 호환)
_LEGACY_STATUS = {"관심": "검토중", "확인필요": "보완필요", "주의": "변리사검토"}


def _ensure_bookmarks(conn):
    conn.executescript(BOOKMARK_SCHEMA)
    # status 컬럼 마이그레이션 (기존 DB 호환)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bookmarks)").fetchall()]
    if "status" not in cols:
        conn.execute("ALTER TABLE bookmarks ADD COLUMN status TEXT DEFAULT '검토중'")
    # 구버전 상태값을 신버전으로 일괄 변환
    for old, new in _LEGACY_STATUS.items():
        conn.execute("UPDATE bookmarks SET status = ? WHERE status = ?",
                     (new, old))


def set_review_status(application_no: str, status: str, title: str = "",
                      applicant: str = "") -> None:
    """검토 상태 저장. status='없음'이면 목록에서 제거."""
    conn = get_connection()
    try:
        _ensure_bookmarks(conn)
        if status in (None, "", "없음"):
            conn.execute("DELETE FROM bookmarks WHERE application_no = ?",
                         (application_no,))
        else:
            conn.execute(
                "INSERT INTO bookmarks(application_no, title, applicant, note,"
                " status, created_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(application_no) DO UPDATE SET status=excluded.status",
                (application_no, title, applicant, "", status,
                 datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_review_status(application_no: str):
    conn = get_connection()
    try:
        _ensure_bookmarks(conn)
        row = conn.execute(
            "SELECT status FROM bookmarks WHERE application_no = ?",
            (application_no,)).fetchone()
        return row["status"] if row else None
    finally:
        conn.close()


def status_map() -> dict:
    """{application_no: status} 전체 매핑 (표 표시·필터용)."""
    conn = get_connection()
    try:
        _ensure_bookmarks(conn)
        rows = conn.execute(
            "SELECT application_no, status FROM bookmarks").fetchall()
        return {r["application_no"]: r["status"] for r in rows}
    finally:
        conn.close()


# --------------------------------------------------------------- bookmarks
def add_bookmark(application_no: str, title: str = "", applicant: str = "",
                 note: str = "") -> None:
    conn = get_connection()
    try:
        _ensure_bookmarks(conn)
        conn.execute(
            "INSERT INTO bookmarks(application_no, title, applicant, note,"
            " created_at) VALUES(?,?,?,?,?) ON CONFLICT(application_no) "
            "DO UPDATE SET note=excluded.note",
            (application_no, title, applicant, note,
             datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def remove_bookmark(application_no: str) -> None:
    conn = get_connection()
    try:
        _ensure_bookmarks(conn)
        conn.execute("DELETE FROM bookmarks WHERE application_no = ?",
                     (application_no,))
        conn.commit()
    finally:
        conn.close()


def is_bookmarked(application_no: str) -> bool:
    conn = get_connection()
    try:
        _ensure_bookmarks(conn)
        row = conn.execute(
            "SELECT 1 FROM bookmarks WHERE application_no = ?",
            (application_no,)).fetchone()
        return row is not None
    finally:
        conn.close()


def list_bookmarks() -> list:
    """북마크된 특허를 patents 테이블과 조인해 전체 정보로 반환."""
    conn = get_connection()
    try:
        _ensure_bookmarks(conn)
        rows = conn.execute(
            "SELECT b.application_no, b.note, b.status AS review_status,"
            " b.created_at AS marked_at, p.* "
            "FROM bookmarks b LEFT JOIN patents p "
            "ON b.application_no = p.application_no "
            "ORDER BY b.created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ----------------------------------------------------------- 검색 이력
def list_ideas(limit: int = 30) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT i.id, i.title, i.description, i.keywords,"
            " i.exclude_keywords, i.idea_dna_json, i.created_at,"
            " COUNT(s.id) AS n_results "
            "FROM ideas i LEFT JOIN search_results s ON s.idea_id = i.id "
            "GROUP BY i.id ORDER BY i.created_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def load_idea_results(idea_id: int) -> list:
    """과거 검색 결과를 patents + search_results 조인으로 복원."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.*, s.vector_score, s.keyword_score, s.dna_score,"
            " s.claim_score, s.ipc_score, s.ai_risk_score, s.total_score,"
            " s.matched_keywords, s.technology_group, s.patent_dna_json,"
            " s.search_query "
            "FROM search_results s JOIN patents p ON p.id = s.patent_id "
            "WHERE s.idea_id = ? ORDER BY s.total_score DESC",
            (idea_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_drawing(patent_id: int, image_path: str, caption: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO drawings(patent_id, image_path, caption, created_at)"
            " VALUES(?,?,?,?)",
            (patent_id, image_path, caption, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ------------------------------------------------------------- 검토 케이스
def save_review_case(case: dict) -> int:
    """검토 케이스를 저장(신규 생성). snapshot 은 결과 전체 JSON."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        now = datetime.now().isoformat()
        cur = conn.execute(
            "INSERT INTO review_cases(idea_id, title, description, keywords,"
            " scope, top_n, status, final_verdict, confidence, n_results,"
            " high_risk, snapshot_json, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (case.get("idea_id"), case.get("title", ""),
             case.get("description", ""), case.get("keywords", ""),
             case.get("scope", "국내"), int(case.get("top_n", 10) or 10),
             case.get("status", "초안"), case.get("final_verdict", ""),
             case.get("confidence", ""), int(case.get("n_results", 0) or 0),
             int(case.get("high_risk", 0) or 0),
             json.dumps(case.get("snapshot", {}), ensure_ascii=False,
                        default=str),
             now, now))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_review_case(case_id: int, **fields) -> None:
    """검토 케이스 일부 필드 갱신 (status, final_verdict 등)."""
    if not fields:
        return
    allowed = {"title", "status", "final_verdict", "confidence",
               "n_results", "high_risk", "snapshot"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "snapshot":
            sets.append("snapshot_json = ?")
            vals.append(json.dumps(v, ensure_ascii=False, default=str))
        else:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(datetime.now().isoformat())
    vals.append(case_id)
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            f"UPDATE review_cases SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def list_review_cases(limit: int = 100) -> list:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        rows = conn.execute(
            "SELECT id, idea_id, title, description, keywords, scope, top_n,"
            " status, final_verdict, confidence, n_results, high_risk,"
            " created_at, updated_at FROM review_cases"
            " ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_review_case(case_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        row = conn.execute(
            "SELECT * FROM review_cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["snapshot"] = json.loads(d.get("snapshot_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["snapshot"] = {}
        return d
    finally:
        conn.close()


def delete_review_case(case_id: int) -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM review_cases WHERE id = ?", (case_id,))
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------- 모니터링 관심조건
def save_monitoring_target(t: dict) -> int:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "INSERT INTO monitoring_targets(name, keywords, ipc, applicant,"
            " scope, enabled, created_at) VALUES(?,?,?,?,?,?,?)",
            (t.get("name", ""), t.get("keywords", ""), t.get("ipc", ""),
             t.get("applicant", ""), t.get("scope", "국내"),
             1 if t.get("enabled", True) else 0,
             datetime.now().isoformat()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_monitoring_targets() -> list:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        rows = conn.execute(
            "SELECT * FROM monitoring_targets ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_monitoring_target(target_id: int) -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM monitoring_targets WHERE id = ?",
                     (target_id,))
        conn.commit()
    finally:
        conn.close()


def touch_monitoring_target(target_id: int) -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "UPDATE monitoring_targets SET last_run_at = ? WHERE id = ?",
            (datetime.now().isoformat(), target_id))
        conn.commit()
    finally:
        conn.close()
