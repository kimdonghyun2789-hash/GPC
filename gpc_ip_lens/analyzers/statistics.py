# -*- coding: utf-8 -*-
"""GPC IP Lens - 통계 생성 모듈 (Tech Landscape / Strategy Board 공용)."""
from typing import List

import pandas as pd

from utils.text_utils import keyword_counts

# 기술 조합 히트맵의 열 (응용 기술)
HEATMAP_COLUMNS = ["접합부", "생산방법", "배수", "센서",
                   "유지관리", "품질관리", "방수", "몰드"]

# 히트맵 행 = 주요 대상 기술 (제목/요약 기반 탐지 키워드)
HEATMAP_ROWS = {
    "중공기둥": ["중공기둥", "중공 기둥", "중공부"],
    "PC기둥": ["pc기둥", "pc 기둥", "프리캐스트 기둥", "프리캐스트기둥"],
    "더블월": ["더블월", "더블 월", "이중벽", "중공벽"],
    "PC보": ["pc보", "pc 보", "프리캐스트 보", "거더"],
    "PC슬래브": ["슬래브", "slab", "데크"],
    "PC부재일반": ["프리캐스트", "pc부재", "pc 부재", "precast"],
}

COLUMN_KEYWORDS = {
    "접합부": ["접합", "이음", "조인트", "연결"],
    "생산방법": ["생산", "제조", "제작", "양생", "성형"],
    "배수": ["배수", "drain", "배출"],
    "센서": ["센서", "계측", "모니터링", "감지"],
    "유지관리": ["유지관리", "점검", "보수", "진단"],
    "품질관리": ["품질", "검사", "결함", "비파괴"],
    "방수": ["방수", "지수", "차수", "수밀"],
    "몰드": ["몰드", "거푸집", "형틀", "탈형"],
}


def to_dataframe(results: List[dict]) -> pd.DataFrame:
    """점수 계산 결과 리스트 → 분석용 DataFrame."""
    df = pd.DataFrame(results)
    if df.empty:
        return df
    df["application_year"] = (
        df["application_date"].astype(str).str[:4]
        .replace({"": "0", "nan": "0", "None": "0"}).astype(int)
    )
    return df


def yearly_counts(df: pd.DataFrame) -> pd.DataFrame:
    """연도별 출원 건수."""
    out = df[df["application_year"] > 0].groupby("application_year").size()
    out = out.reset_index(name="건수").rename(columns={"application_year": "연도"})
    return out


def applicant_top(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    out = df.groupby("applicant").size().sort_values(ascending=False).head(n)
    return out.reset_index(name="건수").rename(columns={"applicant": "출원인"})


def ipc_counts(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    classes = df["ipc"].astype(str).str.split(",").explode().str.strip().str[:4]
    out = classes[classes != ""].value_counts().head(n)
    return out.reset_index(name="건수").rename(columns={"index": "IPC", "ipc": "IPC"})


def status_counts(df: pd.DataFrame) -> pd.DataFrame:
    out = df.groupby("status").size()
    return out.reset_index(name="건수").rename(columns={"status": "상태"})


def group_counts(df: pd.DataFrame) -> pd.DataFrame:
    out = df.groupby("technology_group").size().sort_values(ascending=False)
    return out.reset_index(name="건수").rename(columns={"technology_group": "기술군"})


def keyword_top(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    texts = (df["title"].astype(str) + " " + df["abstract"].astype(str)).tolist()
    pairs = keyword_counts(texts, top_n=n)
    return pd.DataFrame(pairs, columns=["키워드", "빈도"])


def summary_cards(df: pd.DataFrame) -> dict:
    """등록률/소멸률/최근 3년 증가율 요약."""
    total = len(df)
    if total == 0:
        return {"total": 0, "registered_rate": 0, "expired_rate": 0,
                "recent_growth": 0}
    registered = (df["status"] == "등록").sum()
    expired = df["status"].isin(["소멸", "거절", "취하", "포기"]).sum()

    years = df[df["application_year"] > 0]["application_year"]
    recent_growth = 0.0
    if len(years):
        max_year = int(years.max())
        recent = ((years >= max_year - 2) & (years <= max_year)).sum()
        prev = ((years >= max_year - 5) & (years <= max_year - 3)).sum()
        if prev > 0:
            recent_growth = round((recent - prev) / prev * 100, 1)
        elif recent > 0:
            recent_growth = 100.0
    return {
        "total": total,
        "registered_rate": round(registered / total * 100, 1),
        "expired_rate": round(expired / total * 100, 1),
        "recent_growth": recent_growth,
    }


def group_growth(df: pd.DataFrame) -> pd.DataFrame:
    """기술군별 성장률 (최근 3년 vs 그 이전) — 온도맵/Strategy 공용."""
    rows = []
    years = df[df["application_year"] > 0]["application_year"]
    if years.empty:
        return pd.DataFrame(columns=["기술군", "전체", "최근3년", "성장지수"])
    max_year = int(years.max())
    for group, sub in df.groupby("technology_group"):
        sub_years = sub["application_year"]
        recent = ((sub_years >= max_year - 2) & (sub_years <= max_year)).sum()
        prev = (sub_years < max_year - 2).sum()
        growth = round((recent + 1) / (prev + 1), 2)  # 라플라스 평활
        rows.append({"기술군": group, "전체": len(sub),
                     "최근3년": int(recent), "성장지수": growth})
    return pd.DataFrame(rows).sort_values("성장지수", ascending=False)


def tech_combination_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """기술 조합 히트맵: 행=대상 기술, 열=응용 기술, 값=특허 건수."""
    matrix = pd.DataFrame(0, index=list(HEATMAP_ROWS.keys()),
                          columns=HEATMAP_COLUMNS)
    for _, p in df.iterrows():
        text = f"{p.get('title','')} {p.get('abstract','')}".lower()
        row_hits = [r for r, kws in HEATMAP_ROWS.items()
                    if any(k.lower() in text for k in kws)]
        col_hits = [c for c, kws in COLUMN_KEYWORDS.items()
                    if any(k.lower() in text for k in kws)]
        for r in row_hits:
            for c in col_hits:
                matrix.loc[r, c] += 1
    return matrix


def gap_analysis(df: pd.DataFrame) -> List[str]:
    """기술 공백/포화 영역 자동 분석 문장 생성 (Strategy Board)."""
    lines = []
    gc = group_counts(df)
    if gc.empty:
        return ["분석할 데이터가 없습니다. 먼저 Idea Canvas 에서 검색을 실행하세요."]
    total = gc["건수"].sum()
    saturated = gc[gc["건수"] >= total * 0.15]["기술군"].tolist()
    sparse = gc[gc["건수"] <= max(1, total * 0.05)]["기술군"].tolist()
    if saturated:
        lines.append(f"**{', '.join(saturated)}** 영역은 특허가 집중된 포화 영역입니다.")
    if sparse:
        lines.append(f"**{', '.join(sparse)}** 영역은 상대적으로 공백 영역입니다.")
    gg = group_growth(df)
    rising = gg[gg["성장지수"] >= 1.5]["기술군"].tolist()
    if rising:
        lines.append(f"최근 3년간 **{', '.join(rising)}** 관련 출원이 증가하는 추세입니다.")
    high_risk = df[df["total_score"] >= 80] if "total_score" in df else pd.DataFrame()
    if len(high_risk):
        lines.append(
            f"공백 영역이라도 내 아이디어와 유사도 80 이상인 특허가 "
            f"{len(high_risk)}건 존재하므로 주의가 필요합니다.")
    return lines


def survival_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """기술군별 특허 생존성(등록/유지 비율)."""
    rows = []
    for group, sub in df.groupby("technology_group"):
        alive = sub["status"].isin(["등록", "공개"]).sum()
        rows.append({
            "기술군": group, "건수": len(sub),
            "생존(등록+공개)": int(alive),
            "생존율(%)": round(alive / len(sub) * 100, 1),
        })
    return pd.DataFrame(rows).sort_values("생존율(%)", ascending=False)


def applicant_strategy(df: pd.DataFrame, n: int = 8) -> pd.DataFrame:
    """출원인별 주력 기술군/활동 기간 분석."""
    rows = []
    for applicant, sub in df.groupby("applicant"):
        groups = sub.groupby("technology_group").size().sort_values(ascending=False)
        years = sub[sub["application_year"] > 0]["application_year"]
        rows.append({
            "출원인": applicant,
            "건수": len(sub),
            "주력 기술군": groups.index[0] if len(groups) else "-",
            "활동기간": (f"{int(years.min())}~{int(years.max())}"
                       if len(years) else "-"),
            "등록건수": int((sub["status"] == "등록").sum()),
        })
    return (pd.DataFrame(rows).sort_values("건수", ascending=False).head(n))
