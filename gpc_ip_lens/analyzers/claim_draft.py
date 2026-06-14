# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 차별성 도출 및 청구항 초안 (보완안).

유사특허 대비 차별 포인트를 도출하고, 이를 반영한 청구항 초안(독립항/종속항/
방법항/회피설계)을 제안한다. Gemini 가 있으면 정교하게, 없으면 규칙 기반으로
동작한다. 최종 법률 문서가 아닌 변리사 검토용 1차 참고 초안이다.
"""
from typing import List

from analyzers import patent_dna as dna_mod
from services import gemini_service

DISCLAIMER = ("아래 차별성·청구항 초안은 AI/규칙 기반 1차 참고안입니다. "
              "최종 권리범위·출원 가능성은 변리사 검토가 필요합니다.")


def build_differentiation(idea: dict, idea_dna: dict,
                          top_patents: List[dict]) -> dict:
    """내 아이디어 vs 상위 유사특허의 차별 포인트 도출."""
    idea_dna = idea_dna or {}
    common_all, diff_all = set(), set()
    for p in top_patents[:5]:
        p_dna = p.get("patent_dna") or {}
        common, diff = dna_mod.common_and_diff(idea_dna, p_dna)
        common_all |= set(common)
        diff_all |= set(diff)
    # 차별 후보: 내 아이디어에만 있는 토큰(상위 특허 공통구성 제외)
    differentiators = [d for d in diff_all if d not in common_all]
    # 공정단계 차별: 내 아이디어 공정단계 중 특허들에 드문 것
    idea_stages = set(idea_dna.get("stages") or
                      ([idea_dna.get("stage")] if idea_dna.get("stage") else []))
    pat_stages = set()
    for p in top_patents[:5]:
        pat_stages |= set((p.get("patent_dna") or {}).get("stages") or [])
    stage_diff = sorted(idea_stages - pat_stages)
    return {
        "differentiators": sorted(differentiators)[:10],
        "common_points": sorted(common_all)[:10],
        "stage_differentiators": stage_diff,
    }


def _fallback_draft(idea: dict, idea_dna: dict, diff: dict) -> dict:
    idea_dna = idea_dna or {}
    target = (idea_dna.get("target") or idea.get("title")
              or "구조물").strip()
    comps = [c for c in (idea_dna.get("components") or []) if str(c).strip()]
    if not comps:
        from utils.text_utils import split_keywords
        comps = split_keywords(idea.get("keywords", ""))
    comps = comps[:7] or ["주요 구성요소"]
    stages = idea_dna.get("stages") or (
        [idea_dna.get("stage")] if idea_dna.get("stage") else [])
    diffs = diff.get("differentiators", [])

    ind = (f"{target}에 있어서, "
           + ", ".join(f"{c}" for c in comps[:4])
           + " 를 포함하는 것을 특징으로 하는 " + target + ".")
    deps = []
    for c in comps[1:6]:
        deps.append(f"제1항에 있어서, 상기 {c} 는 {target}의 차별 구성으로서 "
                    f"별도의 결합 구조를 갖는 것을 특징으로 하는 " + target + ".")
    # 차별 포인트를 반영한 종속항 보강
    for d in diffs[:2]:
        deps.append(f"제1항에 있어서, {d} 를 더 포함하는 것을 특징으로 하는 "
                    + target + ".")
    deps = deps[:7] or ["제1항에 있어서, 추가 구성을 더 포함하는 것을 특징으로 "
                        "하는 " + target + "."]

    if stages:
        steps = "; ".join(f"{s} 단계" for s in stages)
        method = f"{target}의 시공 방법으로서, {steps}; 를 포함하는 방법."
    else:
        method = (f"{target}의 시공 방법으로서, 구성요소를 제작하는 단계; "
                  "현장에서 조립·접합하는 단계; 를 포함하는 방법.")

    design_around = [f"{d} 를 대체 수단으로 치환하여 동일 효과를 얻는 구성"
                     for d in diffs[:3]]
    if not design_around:
        design_around = ["핵심 구성의 형상/배치를 변경하여 동일 기능을 구현하는 대체안"]

    return {
        "independent_claim": ind,
        "dependent_claims": deps,
        "method_claim": method,
        "design_around": design_around,
        "notes": "규칙 기반 초안입니다. 권리범위·신규성·진보성은 변리사 검토 필요.",
    }


def draft(idea: dict, idea_dna: dict, diff: dict,
          top_patents: List[dict]) -> tuple:
    """청구항 초안 생성. (결과 dict, 방법 'gemini'|'fallback') 반환."""
    if gemini_service.is_available():
        prior = " / ".join(
            str((p.get("patent_dna") or {}).get("solution")
                or p.get("title", ""))[:60] for p in top_patents[:5])
        res = gemini_service.draft_claims(
            idea.get("title", ""), idea.get("description", ""),
            ", ".join(diff.get("differentiators", [])), prior)
        if isinstance(res, dict) and res.get("independent_claim"):
            res.setdefault("dependent_claims", [])
            res.setdefault("design_around", [])
            return res, "gemini"
    return _fallback_draft(idea, idea_dna, diff), "fallback"
