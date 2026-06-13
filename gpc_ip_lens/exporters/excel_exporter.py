# -*- coding: utf-8 -*-
"""GPC IP Lens - Excel 내보내기 (openpyxl 엔진).

시트 구성: Search Results / Similarity Scores / Patent DNA / Statistics /
Technology Groups / AI Review
"""
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import pandas as pd

from analyzers import statistics as stats
from utils import config

RESULT_COLUMNS = [
    "rank", "total_score", "grade", "title", "applicant", "application_no",
    "application_date", "status", "ipc", "cpc", "technology_group",
    "kipris_url",
]

SCORE_COLUMNS = [
    "rank", "title", "total_score", "vector_score", "keyword_score",
    "dna_score", "claim_score", "ipc_score", "ai_risk_score",
    "matched_keywords",
]


def _safe_df(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    cols = [c for c in columns if c in df.columns]
    out = df[cols].copy()
    for c in out.columns:
        out[c] = out[c].apply(
            lambda v: ", ".join(map(str, v)) if isinstance(v, (list, tuple))
            else (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v))
    return out


def _dna_sheet(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in df.iterrows():
        dna = p.get("patent_dna") or {}
        if isinstance(dna, str):
            try:
                dna = json.loads(dna)
            except json.JSONDecodeError:
                dna = {}
        rows.append({
            "title": p.get("title"),
            "application_no": p.get("application_no"),
            "대상": dna.get("target", ""),
            "문제": dna.get("problem", ""),
            "해결수단": dna.get("solution", ""),
            "구성요소": ", ".join(map(str, dna.get("components", []) or [])),
            "적용시점": dna.get("stage", ""),
            "제조/시공방법": dna.get("method", ""),
            "효과": dna.get("effect", ""),
        })
    return pd.DataFrame(rows)


def _review_sheet(review: Optional[dict]) -> pd.DataFrame:
    review = review or {}
    rows = []
    labels = {
        "most_risky_patents": "가장 유사한 특허",
        "common_points": "공통 구성",
        "different_points": "차이 구성",
        "key_differentiators": "핵심 차별 포인트",
        "claim_check_points": "청구항 확인 필요",
        "design_around_points": "회피설계 검토",
        "review_comment": "검토 참고 의견",
    }
    for key, label in labels.items():
        value = review.get(key, "")
        if isinstance(value, list):
            for v in value:
                rows.append({"항목": label, "내용": str(v)})
        elif value:
            rows.append({"항목": label, "내용": str(value)})
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        [{"항목": "-", "내용": "AI 검토 결과 없음"}])


def export_excel(results_df: pd.DataFrame, idea: dict,
                 review: Optional[dict] = None,
                 file_path: Optional[str] = None) -> bytes:
    """전체 분석 결과를 Excel 파일 bytes 로 반환 (file_path 지정 시 저장도)."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _safe_df(results_df, RESULT_COLUMNS).to_excel(
            writer, sheet_name="Search Results", index=False)
        _safe_df(results_df, SCORE_COLUMNS).to_excel(
            writer, sheet_name="Similarity Scores", index=False)
        _dna_sheet(results_df).to_excel(
            writer, sheet_name="Patent DNA", index=False)

        stat_frames = []
        if not results_df.empty:
            yearly = stats.yearly_counts(results_df)
            yearly.insert(0, "구분", "연도별 출원")
            applicants = stats.applicant_top(results_df)
            applicants.insert(0, "구분", "출원인 TOP")
            statuses = stats.status_counts(results_df)
            statuses.insert(0, "구분", "상태별")
            stat_frames = [yearly.rename(columns={"연도": "항목"}),
                           applicants.rename(columns={"출원인": "항목"}),
                           statuses.rename(columns={"상태": "항목"})]
        stats_df = (pd.concat(stat_frames, ignore_index=True)
                    if stat_frames else pd.DataFrame())
        stats_df.to_excel(writer, sheet_name="Statistics", index=False)

        groups_df = (stats.group_counts(results_df)
                     if not results_df.empty else pd.DataFrame())
        groups_df.to_excel(writer, sheet_name="Technology Groups", index=False)
        _review_sheet(review).to_excel(writer, sheet_name="AI Review", index=False)

        # 메타 정보
        meta = pd.DataFrame([
            {"항목": "아이디어명", "내용": idea.get("title", "")},
            {"항목": "아이디어 설명", "내용": idea.get("description", "")},
            {"항목": "핵심 키워드", "내용": idea.get("keywords", "")},
            {"항목": "생성일시", "내용": datetime.now().strftime("%Y-%m-%d %H:%M")},
            {"항목": "프로그램", "내용": "GPC IP Lens"},
        ])
        meta.to_excel(writer, sheet_name="Info", index=False)

    data = buf.getvalue()
    if file_path:
        Path(file_path).write_bytes(data)
    return data


def default_export_path(prefix: str = "gpc_ip_lens") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(config.EXPORTS_DIR / f"{prefix}_{ts}.xlsx")
