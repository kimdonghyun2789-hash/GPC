"""아이디어 DB 관리 (Idea ID 중심)."""
import pandas as pd

from src import storage
from src.utils import now_display, today_compact

IDEA_COLUMNS = [
    "idea_id",
    "created_at",
    "idea_text",
    "keywords",
    "search_scope",
    "top_n",
    "status",
    "review_comment",
    "diff_purpose",
    "diff_structure",
    "diff_stage",
    "diff_effect",
    "total_results",
    "candidate_count",
    "report_html",
    "results_xlsx",
]

COLLECTED_COLUMNS = [
    "idea_id",
    "rank",
    "source",
    "country",
    "grade",
    "score",
    "title",
    "applicant",
    "app_number",
    "pub_number",
    "reg_number",
    "app_date",
    "pub_date",
    "ipc",
    "status",
    "abstract",
    "claims",
    "matched_keywords",
    "review_reason",
    "link",
    "collected_at",
]


def load_ideas() -> pd.DataFrame:
    return storage.load_df(storage.IDEA_DB, IDEA_COLUMNS)


def next_idea_id() -> str:
    """GPC-IP-YYYYMMDD-001 형식으로 당일 일련번호를 증가시킨다."""
    today = today_compact()
    prefix = f"GPC-IP-{today}-"
    ideas = load_ideas()
    existing = [
        idea_id for idea_id in ideas["idea_id"].tolist() if str(idea_id).startswith(prefix)
    ]
    sequence = 1
    if existing:
        numbers = []
        for idea_id in existing:
            tail = str(idea_id).rsplit("-", 1)[-1]
            if tail.isdigit():
                numbers.append(int(tail))
        sequence = (max(numbers) + 1) if numbers else len(existing) + 1
    return f"{prefix}{sequence:03d}"


def save_idea(record: dict) -> None:
    ideas = load_ideas()
    ideas = ideas[ideas["idea_id"] != record["idea_id"]]
    row = {column: str(record.get(column, "")) for column in IDEA_COLUMNS}
    if not row["created_at"]:
        row["created_at"] = now_display()
    ideas = pd.concat([ideas, pd.DataFrame([row])], ignore_index=True)
    storage.save_df(ideas, storage.IDEA_DB)


def update_idea(idea_id: str, **fields) -> None:
    ideas = load_ideas()
    mask = ideas["idea_id"] == idea_id
    if not mask.any():
        return
    for key, value in fields.items():
        if key in IDEA_COLUMNS:
            ideas.loc[mask, key] = str(value)
    storage.save_df(ideas, storage.IDEA_DB)


def get_idea(idea_id: str) -> dict:
    ideas = load_ideas()
    match = ideas[ideas["idea_id"] == idea_id]
    return match.iloc[0].to_dict() if not match.empty else {}


def delete_idea(idea_id: str) -> None:
    ideas = load_ideas()
    storage.save_df(ideas[ideas["idea_id"] != idea_id], storage.IDEA_DB)
    collected = load_collected()
    storage.save_df(
        collected[collected["idea_id"] != idea_id], storage.COLLECTED_DB
    )


def load_collected(idea_id: str = "") -> pd.DataFrame:
    collected = storage.load_df(storage.COLLECTED_DB, COLLECTED_COLUMNS)
    if idea_id:
        return collected[collected["idea_id"] == idea_id]
    return collected


def save_collected(idea_id: str, candidates: list) -> None:
    """해당 아이디어의 기존 수집분을 교체 저장한다."""
    collected = load_collected()
    collected = collected[collected["idea_id"] != idea_id]
    rows = []
    for patent in candidates:
        row = {column: str(patent.get(column, "")) for column in COLLECTED_COLUMNS}
        row["idea_id"] = idea_id
        row["collected_at"] = now_display()
        rows.append(row)
    if rows:
        collected = pd.concat([collected, pd.DataFrame(rows)], ignore_index=True)
    storage.save_df(collected, storage.COLLECTED_DB)
