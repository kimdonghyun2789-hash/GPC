# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 기술발전도(Technology Timeline) 생성."""
from typing import List

import pandas as pd

from services import gemini_service
from utils.text_utils import keyword_counts


def yearly_keywords(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """연도별 주요 키워드 추출."""
    rows = []
    for year, sub in df[df["application_year"] > 0].groupby("application_year"):
        texts = (sub["title"].astype(str) + " " + sub["abstract"].astype(str)).tolist()
        kws = [k for k, _ in keyword_counts(texts, top_n=top_n)]
        rows.append({"연도": int(year), "건수": len(sub),
                     "주요 키워드": ", ".join(kws)})
    return pd.DataFrame(rows).sort_values("연도")


def group_year_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """기술군 x 연도 출원 건수 매트릭스."""
    sub = df[df["application_year"] > 0]
    if sub.empty:
        return pd.DataFrame()
    return pd.crosstab(sub["technology_group"], sub["application_year"])


def first_appearance(df: pd.DataFrame) -> pd.DataFrame:
    """기술군별 최초 등장 연도."""
    sub = df[df["application_year"] > 0]
    if sub.empty:
        return pd.DataFrame(columns=["기술군", "최초 등장"])
    out = sub.groupby("technology_group")["application_year"].min()
    return (out.reset_index(name="최초 등장")
            .rename(columns={"technology_group": "기술군"})
            .sort_values("최초 등장"))


def rising_groups(df: pd.DataFrame) -> List[str]:
    """최근 3년간 증가 추세인 기술군."""
    from analyzers.statistics import group_growth
    gg = group_growth(df)
    return gg[gg["성장지수"] >= 1.5]["기술군"].tolist()


def _era_label(years: List[int]) -> str:
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}~{years[-1]}"


def fallback_narrative(df: pd.DataFrame) -> List[str]:
    """Gemini 실패 시: 연도별 키워드/기술군 데이터를 기반으로 자동 문장 생성."""
    sub = df[df["application_year"] > 0]
    if sub.empty:
        return ["연도 정보가 있는 특허가 없어 기술발전도를 생성할 수 없습니다."]
    years = sorted(sub["application_year"].unique())
    # 전체 기간을 3~4개 구간으로 분할
    n_bins = min(4, max(2, len(years) // 3)) if len(years) > 1 else 1
    bin_size = max(1, (len(years) + n_bins - 1) // n_bins)
    lines = []
    for i in range(0, len(years), bin_size):
        era_years = years[i:i + bin_size]
        era_df = sub[sub["application_year"].isin(era_years)]
        groups = era_df.groupby("technology_group").size().sort_values(ascending=False)
        texts = (era_df["title"].astype(str) + " " + era_df["abstract"].astype(str)).tolist()
        kws = [k for k, _ in keyword_counts(texts, top_n=3)]
        top_groups = ", ".join(groups.index[:2])
        lines.append(
            f"**{_era_label([int(y) for y in era_years])}**: "
            f"{top_groups} 중심 ({len(era_df)}건, 주요 키워드: {', '.join(kws)})")
    rising = rising_groups(df)
    if rising:
        lines.append(f"**최근 증가 기술군**: {', '.join(rising)}")
    return lines


def narrative(df: pd.DataFrame) -> tuple:
    """기술발전 흐름 문장화. (불릿 리스트, 방법명) 반환."""
    if gemini_service.is_available():
        yk = yearly_keywords(df)
        fa = first_appearance(df)
        summary = (
            "연도별 출원/키워드:\n" + yk.to_string(index=False)
            + "\n\n기술군 최초 등장 연도:\n" + fa.to_string(index=False)
            + "\n\n최근 증가 기술군: " + ", ".join(rising_groups(df))
        )
        text = gemini_service.narrate_timeline(summary)
        if text:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            return lines, "gemini"
    return fallback_narrative(df), "fallback"
