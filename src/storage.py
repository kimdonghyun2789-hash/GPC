"""data/ 폴더의 CSV + Excel 동시 저장/불러오기."""
import pandas as pd

from src import config

IDEA_DB = "idea_database"
COLLECTED_DB = "collected_patents"
FAVORITES_DB = "favorite_patents"


def load_df(name: str, columns: list) -> pd.DataFrame:
    """CSV를 기준 저장소로 사용하고, 없으면 빈 DataFrame을 반환한다."""
    config.ensure_dirs()
    csv_path = config.DATA_DIR / f"{name}.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path, dtype=str).fillna("")
        except Exception:
            return pd.DataFrame(columns=columns)
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        return df[columns]
    return pd.DataFrame(columns=columns)


def save_df(df: pd.DataFrame, name: str) -> None:
    """CSV와 Excel을 함께 저장한다."""
    config.ensure_dirs()
    csv_path = config.DATA_DIR / f"{name}.csv"
    xlsx_path = config.DATA_DIR / f"{name}.xlsx"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    try:
        df.to_excel(xlsx_path, index=False)
    except Exception:
        # Excel 파일이 열려 있는 경우 등 — CSV 저장은 유지한다.
        pass
