# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 건설/PC 도메인 사전.

프리캐스트 콘크리트(PC) 공정 단계·구성요소·효과 등 도메인 어휘를 모아
검색어 확장·특허 DNA·구성요소 매칭에서 공통으로 사용한다.
"""
from typing import List

# 공정 단계 (생산 → 유지관리). 순서는 실제 공정 흐름을 따른다.
PROCESS_STAGES = ["생산", "탈형", "운반", "양중", "설치",
                  "접합", "충전", "양생", "유지관리"]

# 각 공정 단계를 판정하는 단서 어휘
STAGE_HINTS = {
    "생산": ["생산", "제작", "제조", "타설", "성형", "몰드", "거푸집", "형틀",
            "캐스팅", "casting"],
    "탈형": ["탈형", "탈거", "분리", "demold", "demoulding"],
    "운반": ["운반", "이송", "반입", "상차", "하차", "운송", "transport"],
    "양중": ["양중", "인양", "리프팅", "크레인", "거치대", "lifting", "hoisting"],
    "설치": ["설치", "거치", "조립", "시공", "설치오차", "install", "erection"],
    "접합": ["접합", "연결", "이음", "조인트", "전단키", "정착", "연결재",
            "joint", "connection", "shear key"],
    "충전": ["충전", "주입", "그라우트", "그라우팅", "모르타르", "무수축",
            "grout", "filling"],
    "양생": ["양생", "경화", "증기양생", "수화", "curing"],
    "유지관리": ["유지관리", "점검", "보수", "보강", "계측", "모니터링", "진단",
              "maintenance", "inspection", "monitoring"],
}

# 대표 구성요소(부재) 어휘 — 구성요소 분해 보조
COMPONENT_TERMS = [
    "기둥", "보", "슬래브", "벽체", "패널", "거더", "기초", "중공부",
    "전단키", "슬리브", "커플러", "철근", "정착구", "배수구", "배수관",
    "포트", "필터", "마개", "앵커", "전단연결재", "더블월", "하프슬래브",
]

# 효과 어휘 — 효과 추출 보조
EFFECT_TERMS = [
    "공기단축", "원가절감", "품질향상", "내구성", "시공성", "안전성",
    "누수방지", "균열방지", "경량화", "정밀도", "생산성", "유지보수성",
]


def _norm(text) -> str:
    return str(text or "").lower()


def detect_stages(text) -> List[str]:
    """텍스트에서 등장하는 공정 단계를 공정 순서대로 반환."""
    t = _norm(text)
    found = []
    for stage in PROCESS_STAGES:
        if any(h.lower() in t for h in STAGE_HINTS[stage]):
            found.append(stage)
    return found


def primary_stage(text) -> str:
    """가장 핵심으로 보이는 단일 공정 단계(없으면 '')."""
    stages = detect_stages(text)
    return stages[0] if stages else ""


def detect_components(text) -> List[str]:
    """텍스트에서 등장하는 대표 구성요소(부재)."""
    t = _norm(text)
    return [c for c in COMPONENT_TERMS if c.lower() in t]


def detect_effects(text) -> List[str]:
    t = _norm(text)
    return [e for e in EFFECT_TERMS if e.lower() in t]
