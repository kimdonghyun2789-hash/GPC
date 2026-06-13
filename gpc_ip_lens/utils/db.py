# -*- coding: utf-8 -*-
"""GPC IP Lens - SQLite 데이터베이스 모듈."""
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
        for table in ("search_results", "drawings", "patents", "ideas"):
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
