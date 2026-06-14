# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 모니터링 데이터 소스 (MVP: 더미/파생).

대시보드·기술 모니터링·경쟁사 분석·알림·포트폴리오 화면에 쓰는 데이터를
제공한다. 현재는 sample_patents.csv(특허 유니버스)에서 결정적으로 파생하며,
추후 실제 KIPRIS 모니터링 API로 이 함수들의 내부만 교체하면 된다.

데이터 구조(향후 API 연동 고려):
- 관심 조건(monitoring targets)은 settings/DB에 저장(키워드·IPC·출원인 등)
- 각 함수는 '관심 조건에 매칭되는 최신 특허 현황'을 반환하는 형태로 설계
"""
import datetime as _dt
from typing import List

import pandas as pd

from utils import config

_universe = None


def _load_universe() -> pd.DataFrame:
    global _universe
    if _universe is None:
        df = pd.read_csv(config.SAMPLE_CSV, dtype=str).fillna("")
        df["year"] = (df["application_date"].astype(str).str[:4]
                      .replace({"": "0"}).astype(int))
        _universe = df
    return _universe.copy()


def last_updated() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def dashboard_stats(results_df=None, worklist=None) -> dict:
    """대시보드 상단 카드용 지표 (유니버스 기반 파생 + 현재 검색/관심 반영)."""
    u = _load_universe()
    max_y = int(u[u["year"] > 0]["year"].max()) if len(u) else 0
    recent = u[u["year"] >= max_y - 1]              # 최근 ~2년을 '신규'로 간주
    n_results = 0 if results_df is None else len(results_df)
    risky = 0
    if results_df is not None and "total_score" in results_df:
        risky = int((results_df["total_score"] >= 70).sum())
    n_watch = 0 if not worklist else len(worklist)
    return {
        "watch_total": n_watch,
        "new_published": int((recent["status"] == "공개").sum()),
        "new_registered": int((recent["status"] == "등록").sum()),
        "new_similar_30d": n_results or int(len(recent)),
        "competitor_new": int(recent.groupby("applicant").ngroups),
        "high_risk": risky or int((u["status"] == "등록").sum() // 4),
        "review_needed": n_watch or len(alerts()),
        "updated": last_updated(),
    }


def yearly_trend() -> pd.DataFrame:
    u = _load_universe()
    s = u[u["year"] > 0].groupby("year").size()
    return s.reset_index(name="건수").rename(columns={"year": "연도"})


def status_distribution() -> pd.DataFrame:
    u = _load_universe()
    s = u.groupby("status").size()
    return s.reset_index(name="건수").rename(columns={"status": "상태"})


def ipc_distribution(n: int = 8) -> pd.DataFrame:
    u = _load_universe()
    cls = u["ipc"].astype(str).str.split(",").explode().str.strip().str[:4]
    s = cls[cls != ""].value_counts().head(n)
    return s.reset_index(name="건수").rename(columns={"index": "IPC", "ipc": "IPC"})


def competitor_table(n: int = 8) -> pd.DataFrame:
    """출원인(경쟁사)별 출원 현황 + 최근 신규."""
    u = _load_universe()
    max_y = int(u[u["year"] > 0]["year"].max()) if len(u) else 0
    rows = []
    for appl, sub in u.groupby("applicant"):
        recent = int((sub["year"] >= max_y - 1).sum())
        regs = int((sub["status"] == "등록").sum())
        rows.append({"경쟁사": appl, "총 출원": len(sub), "최근 신규": recent,
                     "등록": regs,
                     "주력 기술군": sub["technology_group"].mode().iloc[0]
                     if len(sub) else "-"})
    return (pd.DataFrame(rows).sort_values("총 출원", ascending=False).head(n))


def recent_patents(n: int = 8) -> List[dict]:
    """최근 공개/등록된 특허 (신규 모니터링 리스트)."""
    u = _load_universe().sort_values("application_date", ascending=False)
    return u.head(n).to_dict("records")


# 알림 중요도
_ALERT_LEVELS = {"높음": "고위험", "중간": "주의", "낮음": "참고"}


def alerts() -> List[dict]:
    """관심 조건 변화 알림 (유니버스에서 결정적으로 파생)."""
    u = _load_universe().sort_values("application_date", ascending=False)
    out = []
    for _, r in u.head(12).iterrows():
        st = r["status"]
        if st == "등록":
            typ, lvl, msg = "등록", "중간", "관심 특허가 등록되었습니다"
        elif st == "공개":
            typ, lvl, msg = "신규공개", "낮음", "신규 유사 특허가 공개되었습니다"
        else:
            typ, lvl, msg = "상태변경", "낮음", "관심 특허 상태가 변경되었습니다"
        out.append({
            "type": typ, "level": lvl, "title": r["title"],
            "applicant": r["applicant"], "date": r["application_date"],
            "application_no": r["application_no"],
            "message": f"{msg} · {r['applicant']}",
        })
    # 고위험 알림 하나 (가장 최근 등록건)
    reg = u[u["status"] == "등록"].head(1)
    if len(reg):
        rr = reg.iloc[0]
        out.insert(0, {
            "type": "고위험유사", "level": "높음", "title": rr["title"],
            "applicant": rr["applicant"], "date": rr["application_date"],
            "application_no": rr["application_no"],
            "message": "내 아이디어와 높은 유사도의 신규 특허가 발견되었습니다",
        })
    return out


def alert_counts() -> dict:
    c = {"높음": 0, "중간": 0, "낮음": 0}
    for a in alerts():
        c[a["level"]] = c.get(a["level"], 0) + 1
    return c
