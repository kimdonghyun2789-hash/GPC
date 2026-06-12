"""유사특허 분석 결과에 대한 기본 통계."""
from collections import Counter

import pandas as pd

from src.utils import extract_year


def _first_applicant(applicant: str) -> str:
    value = str(applicant or "").strip()
    for separator in (";", "|", ","):
        if separator in value:
            value = value.split(separator)[0].strip()
            break
    return value


def _ipc_main_class(ipc: str) -> str:
    code = str(ipc or "").strip()
    return code[:4].upper().replace(" ", "") if code else ""


def build_statistics(all_patents: list, candidates: list) -> dict:
    """검색 전체 결과와 유사특허 후보를 받아 기본 통계를 만든다."""
    country_counts = Counter(p.get("source") or "기타" for p in all_patents)

    year_counts = Counter()
    for patent in all_patents:
        year = extract_year(patent.get("pub_date"), patent.get("app_date"))
        if year:
            year_counts[year] += 1

    applicant_counts = Counter()
    for patent in all_patents:
        applicant = _first_applicant(patent.get("applicant"))
        if applicant:
            applicant_counts[applicant] += 1

    ipc_counts = Counter()
    for patent in all_patents:
        ipc = _ipc_main_class(patent.get("ipc"))
        if ipc:
            ipc_counts[ipc] += 1

    grade_counts = Counter(p.get("grade") or "참고 수준" for p in candidates)

    year_df = pd.DataFrame(
        sorted(year_counts.items()), columns=["연도", "건수"]
    ).set_index("연도")
    applicant_df = pd.DataFrame(
        applicant_counts.most_common(10), columns=["출원인", "건수"]
    )
    ipc_df = pd.DataFrame(ipc_counts.most_common(10), columns=["IPC/CPC", "건수"])
    country_df = pd.DataFrame(
        sorted(country_counts.items()), columns=["국가/출처", "건수"]
    )
    grade_order = ["매우 유사", "유사", "일부 유사", "참고 수준"]
    grade_df = pd.DataFrame(
        [(g, grade_counts.get(g, 0)) for g in grade_order],
        columns=["유사도 등급", "건수"],
    )

    return {
        "total_results": len(all_patents),
        "candidate_count": len(candidates),
        "country_df": country_df,
        "year_df": year_df,
        "applicant_df": applicant_df,
        "ipc_df": ipc_df,
        "grade_df": grade_df,
    }
