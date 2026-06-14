# -*- coding: utf-8 -*-
"""IP³ - 아이디어 ↔ 유사특허 차이 비교 엔진.

내 아이디어와 유사특허를 항목별(적용 대상/공정 단계/문제/해결수단/핵심 구성/
작용 원리/효과/청구항 구성/권리화 포인트)로 비교해 일치 여부·차이점·예비 리스크·
차별화 가능성·보완 방향을 표로 만든다. 규칙 기반으로 동작(키 불필요)하며,
최종 법률 판단이 아닌 1차 검토 참고 자료다.
"""
from typing import List

from analyzers import patent_dna as dna_mod
from utils.text_utils import tokenize

DISCLAIMER = ("※ 차이 비교는 규칙 기반 1차 참고 자료이며 최종 법률 판단이 "
              "아닙니다. 권리범위 충돌 가능성은 변리사 검토가 필요합니다.")

# (표시명, idea_dna/patent_dna 필드 키 또는 특수 처리 키)
COMPARE_ITEMS = [
    ("적용 대상", "target"),
    ("공정 단계", "stages"),
    ("해결하려는 문제", "problem"),
    ("해결수단", "solution"),
    ("핵심 구성", "components"),
    ("작용 원리", "_principle"),     # 해결수단+효과에서 파생
    ("효과", "effect"),
    ("청구항 구성", "_claim"),       # 특허 대표청구항 원문 기반
    ("권리화 포인트", "_rights"),    # 핵심 구성+청구항에서 파생
]

VERDICTS = ["일치", "부분일치", "차이", "미확인"]


def _text(value) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value or "")


def _idea_value(idea: dict, idea_dna: dict, key: str) -> str:
    if key == "_principle":
        return f"{_text(idea_dna.get('solution'))} {_text(idea_dna.get('effect'))}"
    if key == "_claim":
        # 아이디어는 청구항 원문이 없으므로 구성요소+키워드로 대체
        return f"{_text(idea_dna.get('components'))} {idea.get('keywords','')}"
    if key == "_rights":
        return _text(idea_dna.get("components"))
    return _text(idea_dna.get(key))


def _patent_value(patent: dict, p_dna: dict, key: str) -> tuple:
    """(표시 텍스트, 비교 텍스트, 청구항원문여부) 반환."""
    claim = str(patent.get("representative_claim", "")).strip()
    if key == "_principle":
        return (_text(p_dna.get("solution")) or "-",
                f"{_text(p_dna.get('solution'))} {_text(p_dna.get('effect'))}",
                True)
    if key == "_claim":
        disp = claim[:160] if claim else "청구항 원문 미확보"
        return (disp, claim, bool(claim))
    if key == "_rights":
        return (_text(p_dna.get("components")) or "-",
                f"{_text(p_dna.get('components'))} {claim}", True)
    val = _text(p_dna.get(key))
    return (val or "-", val, True)


def _has_overlap(idea_v: str, pat_v: str) -> bool:
    """부분 문자열 수준의 겹침 여부(한국어 복합어 대응)."""
    a, b = set(tokenize(idea_v)), set(tokenize(pat_v))
    if a & b:
        return True
    return any(x in y or y in x for x in a for y in b if len(x) >= 2)


def _verdict(sim: float, idea_v: str, pat_v: str, claim_ok: bool) -> str:
    if not claim_ok:
        return "미확인"
    if not idea_v.strip() or not pat_v.strip():
        return "미확인"
    if sim >= 0.5:
        return "일치"
    if sim >= 0.18 or _has_overlap(idea_v, pat_v):
        return "부분일치"
    return "차이"


_RISK_BY_VERDICT = {"일치": "높음", "부분일치": "중간", "차이": "낮음",
                    "미확인": "판단보류"}
_DIFF_BY_VERDICT = {"일치": "낮음", "부분일치": "보통", "차이": "높음",
                    "미확인": "추가검토"}
_GUIDE_BY_VERDICT = {
    "일치": "겹치는 구성 — 한정/추가 요소로 차별화 필요",
    "부분일치": "일부 겹침 — 세부 한정으로 차별 강화 권장",
    "차이": "차별 포인트 — 청구항에 명확히 명시 권장",
    "미확인": "원문 확인 후 재검토 필요",
}


def build_diff_table(idea: dict, idea_dna: dict, patent: dict,
                     p_dna: dict = None) -> List[dict]:
    """내 아이디어 vs 특정 유사특허 1건의 항목별 차이 비교표."""
    idea_dna = idea_dna or {}
    p_dna = p_dna or patent.get("patent_dna") or {}
    if isinstance(p_dna, str):
        import json
        try:
            p_dna = json.loads(p_dna)
        except (ValueError, TypeError):
            p_dna = {}
    rows = []
    for label, key in COMPARE_ITEMS:
        idea_v = _idea_value(idea, idea_dna, key)
        pat_disp, pat_cmp, claim_ok = _patent_value(patent, p_dna, key)
        sim = dna_mod.field_similarity(idea_v, pat_cmp)
        verdict = _verdict(sim, idea_v, pat_cmp, claim_ok)
        # 차이점 요약 (간단 토큰 차집합)
        only_idea = sorted(set(tokenize(idea_v)) - set(tokenize(pat_cmp)))[:4]
        rows.append({
            "비교 항목": label,
            "내 아이디어": (idea_v[:80] or "-"),
            "유사특허": (pat_disp[:80] or "-"),
            "일치 여부": verdict,
            "차이점": (", ".join(only_idea) or "-"),
            "예비 리스크": _RISK_BY_VERDICT[verdict],
            "차별화 가능성": _DIFF_BY_VERDICT[verdict],
            "보완 방향": _GUIDE_BY_VERDICT[verdict],
        })
    return rows


def summary(rows: List[dict]) -> dict:
    c = {v: 0 for v in VERDICTS}
    for r in rows:
        c[r.get("일치 여부", "미확인")] = c.get(r.get("일치 여부", "미확인"), 0) + 1
    return c


def aggregate(idea: dict, idea_dna: dict, top_patents: List[dict]) -> dict:
    """TOP N 전체 기준 공통점/차이점/위험요소/차별화 포인트 요약."""
    idea_dna = idea_dna or {}
    common, diff = set(), set()
    high_risk_items = []
    for p in top_patents[:5]:
        rows = build_diff_table(idea, idea_dna, p)
        for r in rows:
            if r["일치 여부"] in ("일치", "부분일치"):
                common.add(r["비교 항목"])
                if r["예비 리스크"] == "높음":
                    high_risk_items.append(f"{r['비교 항목']}({p.get('title','')[:20]})")
            elif r["일치 여부"] == "차이":
                diff.add(r["비교 항목"])
    return {
        "공통_항목": sorted(common),
        "차이_항목": sorted(diff),
        "위험_요소": high_risk_items[:8],
        "차별_포인트": sorted(diff)[:8],
    }
