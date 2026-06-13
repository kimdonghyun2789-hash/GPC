# -*- coding: utf-8 -*-
"""GPC IP Lens - 기술군 분류기 (키워드 규칙 + IPC 보정)."""
from typing import List

TECH_GROUPS = [
    "접합부", "전단키", "생산방법", "몰드", "배수", "방수",
    "품질관리", "유지관리", "센서", "시공장비", "기타",
]

# 기술군별 키워드 규칙
GROUP_KEYWORDS = {
    "접합부": ["접합", "이음", "조인트", "joint", "connection", "연결부",
              "정착", "커플러", "접속"],
    "전단키": ["전단키", "전단연결", "전단돌기", "shear key", "전단저항",
              "합성거동", "전단보강"],
    "생산방법": ["생산", "제조", "제작", "양생", "타설", "성형", "production",
               "manufacturing", "공장"],
    "몰드": ["몰드", "거푸집", "형틀", "mold", "form", "탈형"],
    "배수": ["배수", "drain", "배출", "유공", "집수", "배수관", "배수구"],
    "방수": ["방수", "지수", "차수", "waterproof", "수밀", "실링", "씰"],
    "품질관리": ["품질", "검사", "quality", "결함", "비파괴", "강도측정"],
    "유지관리": ["유지관리", "점검", "보수", "maintenance", "진단", "열화"],
    "센서": ["센서", "sensor", "계측", "모니터링", "IoT", "감지"],
    "시공장비": ["장비", "크레인", "인양", "리프팅", "거치", "운반", "조립장치"],
}

# IPC 메인클래스 → 기술군 보정 (보조 신호로만 사용)
IPC_HINTS = {
    "B28B": "생산방법",   # 점토/시멘트 성형
    "E04G": "시공장비",   # 비계/거푸집/시공보조
    "E03F": "배수",       # 하수/배수
    "G01N": "품질관리",   # 재료 시험
    "G01M": "품질관리",
}


def classify_text(text: str, ipc: str = "") -> str:
    """텍스트(제목+요약+청구항)와 IPC 로 기술군 1개를 결정한다."""
    if not text:
        return "기타"
    low = str(text).lower()
    scores = {}
    for group, kws in GROUP_KEYWORDS.items():
        score = sum(low.count(kw.lower()) for kw in kws)
        if score > 0:
            scores[group] = score
    # IPC 보정: 해당 기술군에 +2
    for prefix, group in IPC_HINTS.items():
        if prefix in str(ipc):
            scores[group] = scores.get(group, 0) + 2
    if not scores:
        return "기타"
    return max(scores.items(), key=lambda x: x[1])[0]


def classify_patent(patent: dict) -> str:
    """특허 dict 를 기술군으로 분류. CSV에 technology_group 이 있으면 우선."""
    given = str(patent.get("technology_group") or "").strip()
    if given and given in TECH_GROUPS:
        return given
    text = " ".join([
        str(patent.get("title", "")),
        str(patent.get("abstract", "")),
        str(patent.get("representative_claim", "")),
    ])
    return classify_text(text, patent.get("ipc", ""))


def classify_many(patents: List[dict]) -> List[str]:
    return [classify_patent(p) for p in patents]
