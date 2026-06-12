"""관심특허 저장/관리."""
import pandas as pd

from src import storage
from src.utils import now_display

FAVORITE_COLUMNS = [
    "idea_id",
    "title",
    "applicant",
    "source",
    "country",
    "grade",
    "app_number",
    "pub_number",
    "ipc",
    "matched_keywords",
    "review_reason",
    "review_comment",
    "link",
    "added_at",
]


def load_favorites(idea_id: str = "") -> pd.DataFrame:
    favorites = storage.load_df(storage.FAVORITES_DB, FAVORITE_COLUMNS)
    if idea_id:
        return favorites[favorites["idea_id"] == idea_id]
    return favorites


def _key(record) -> tuple:
    return (
        str(record.get("idea_id", "")),
        str(record.get("pub_number", "")) or str(record.get("title", "")),
    )


def is_favorite(idea_id: str, patent: dict) -> bool:
    favorites = load_favorites(idea_id)
    target = _key({**patent, "idea_id": idea_id})
    return any(_key(row) == target for _, row in favorites.iterrows())


def add_favorite(idea_id: str, patent: dict, comment: str = "") -> bool:
    """이미 저장된 특허면 False를 반환한다."""
    if is_favorite(idea_id, patent):
        return False
    favorites = load_favorites()
    row = {column: str(patent.get(column, "")) for column in FAVORITE_COLUMNS}
    row["idea_id"] = idea_id
    row["review_comment"] = comment
    row["added_at"] = now_display()
    favorites = pd.concat([favorites, pd.DataFrame([row])], ignore_index=True)
    storage.save_df(favorites, storage.FAVORITES_DB)
    return True


def update_comment(idea_id: str, pub_or_title: str, comment: str) -> None:
    favorites = load_favorites()
    mask = (favorites["idea_id"] == idea_id) & (
        (favorites["pub_number"] == pub_or_title)
        | (favorites["title"] == pub_or_title)
    )
    favorites.loc[mask, "review_comment"] = str(comment)
    storage.save_df(favorites, storage.FAVORITES_DB)


def remove_favorite(idea_id: str, pub_or_title: str) -> None:
    favorites = load_favorites()
    mask = (favorites["idea_id"] == idea_id) & (
        (favorites["pub_number"] == pub_or_title)
        | (favorites["title"] == pub_or_title)
    )
    storage.save_df(favorites[~mask], storage.FAVORITES_DB)
