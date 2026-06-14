# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - AI 1차 특허 검토 (Gemini + fallback).

주의: 출력은 참고 의견이며 최종 법률 판단이 아니다. '출원 가능' 같은
단정 표현을 쓰지 않고 '검토 가능성 있음 / 변리사 검토 필요'로 표현한다.
"""
import json
from typing import List

from analyzers import patent_dna as dna_mod
from services import gemini_service

DISCLAIMER = (
    "※ 본 결과는 AI 기반 1차 참고 의견이며 최종 법률 판단이 아닙니다. "
    "출원 여부 결정 전 추가 선행기술 조사와 변리사 검토가 필요합니다."
)

EMPTY_REVIEW = {
    "most_risky_patents": [], "common_points": [], "different_points": [],
    "key_differentiators": [], "claim_check_points": [],
    "design_around_points": [], "review_comment": "",
}


def _build_review_input(idea: dict, idea_dna: dict, top_patents: List[dict]) -> str:
    lines = [
        f"내 아이디어: {idea.get('title','')}",
        f"설명: {idea.get('description','')}",
        f"아이디어 DNA: {json.dumps(idea_dna, ensure_ascii=False)}",
        "",
        "유사특허 TOP:",
    ]
    for p in top_patents:
        lines.append(
            f"- [{p.get('rank')}위, 유사도 {p.get('total_score')}] {p.get('title')}"
            f" / 출원인 {p.get('applicant')} / 상태 {p.get('status')}\n"
            f"  요약: {str(p.get('abstract',''))[:300]}\n"
            f"  대표청구항: {str(p.get('representative_claim',''))[:300]}\n"
            f"  특허 DNA: {json.dumps(p.get('patent_dna', {}), ensure_ascii=False)}\n"
            f"  도면 캡션: {p.get('drawing_caption','')}"
        )
    return "\n".join(lines)


def fallback_review(idea: dict, idea_dna: dict, top_patents: List[dict]) -> dict:
    """Gemini 실패 시 규칙 기반 검토 결과 생성."""
    review = {k: list(v) if isinstance(v, list) else v
              for k, v in EMPTY_REVIEW.items()}
    if not top_patents:
        review["review_comment"] = (
            "비교할 유사특허가 없습니다. 검색 범위를 넓혀 추가 선행기술 확인이 "
            "필요합니다. " + DISCLAIMER)
        return review

    high = [p for p in top_patents if p.get("total_score", 0) >= 80]
    mid = [p for p in top_patents if 60 <= p.get("total_score", 0) < 80]

    for p in (high + mid)[:5]:
        review["most_risky_patents"].append(
            f"{p['title']} (유사도 {p['total_score']}, {p.get('applicant','')})")

    common_all, diff_all = set(), set()
    for p in top_patents[:5]:
        common, diff = dna_mod.common_and_diff(idea_dna, p.get("patent_dna", {}))
        common_all.update(common[:5])
        diff_all.update(diff[:5])
    review["common_points"] = sorted(common_all)[:10]
    review["different_points"] = sorted(diff_all)[:10]
    review["key_differentiators"] = [
        f"'{d}' 관련 구성은 상위 유사특허 DNA에서 확인되지 않음 — 차별 포인트 후보"
        for d in sorted(diff_all)[:5]
    ]
    for p in (high + mid)[:3]:
        review["claim_check_points"].append(
            f"{p['title']}의 대표청구항에서 "
            f"'{', '.join(p.get('matched_keywords', [])[:3])}' 관련 한정사항 확인 필요")
        review["design_around_points"].append(
            f"{p['title']} 대비 결합구조/적용시점을 달리하는 회피설계 검토 가능")

    if high:
        comment = (f"유사도 80 이상 특허가 {len(high)}건 존재하므로 신중한 검토가 "
                   "필요합니다. 해당 특허들의 청구항 전체 확인 및 변리사 검토가 필요합니다.")
    elif mid:
        comment = (f"유사도 60~79 특허가 {len(mid)}건 있습니다. 차별 포인트를 "
                   "명확히 하면 출원 검토 가능성이 있으나, 추가 선행기술 확인이 필요합니다.")
    else:
        comment = ("현재 검색 범위에서는 고유사 특허가 확인되지 않았습니다. "
                   "출원 검토 가능성이 있으나, 검색식을 넓힌 추가 선행기술 확인이 필요합니다.")
    review["review_comment"] = comment + " " + DISCLAIMER
    return review


def run_review(idea: dict, idea_dna: dict, top_patents: List[dict]) -> tuple:
    """AI 검토 실행. (결과 dict, 방법 'gemini'|'fallback') 반환."""
    if gemini_service.is_available():
        result = gemini_service.review_patents(
            _build_review_input(idea, idea_dna, top_patents))
        if result and isinstance(result, dict) and result.get("review_comment"):
            merged = {k: result.get(k, v) for k, v in EMPTY_REVIEW.items()}
            if DISCLAIMER not in str(merged["review_comment"]):
                merged["review_comment"] = str(merged["review_comment"]) + " " + DISCLAIMER
            return merged, "gemini"
    return fallback_review(idea, idea_dna, top_patents), "fallback"
