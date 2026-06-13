# -*- coding: utf-8 -*-
"""GPC IP Lens - 청구항 대비표 (Claim Chart).

핵심 특허의 대표청구항을 구성요소(element) 단위로 분해하고, 각 구성요소가
내 아이디어에 대응되는지(일치/부분/차이)를 비교한다. 변리사·출원 검토의
1차 자료로 쓰되 최종 법률 판단이 아님을 명시한다.
"""
import json
import re
from typing import List

from services import gemini_service
from utils.text_utils import jaccard, tokenize

DISCLAIMER = ("※ 청구항 대비표는 AI 1차 분석 참고 자료이며 최종 법률 판단이 "
              "아닙니다. 침해/유효성 판단은 변리사 검토가 필요합니다.")


def split_claim_elements(claim: str) -> List[str]:
    """대표청구항을 구성요소 단위로 분해 (규칙 기반)."""
    if not claim:
        return []
    text = re.sub(r"청구항\s*\d+\s*[.:]?", "", str(claim)).strip()
    # 구성요소 경계: '~와/과', '~및', '~포함하는', 쉼표, '하고' 등
    parts = re.split(r"(?:와|과|및|,|;|그리고|아울러)\s+(?=[가-힣A-Za-z])"
                     r"|(?<=하는)\s+|(?<=되는)\s+", text)
    elements = []
    for p in parts:
        p = p.strip(" .,;")
        if len(p) >= 6:
            elements.append(p[:120])
    # 너무 잘게 쪼개졌으면 문장 단위로 대체
    if len(elements) > 12 or not elements:
        elements = [s.strip()[:120] for s in re.split(r"[.\n]", text)
                    if len(s.strip()) >= 6][:10]
    return elements[:12]


def _idea_corpus(idea: dict, idea_dna: dict) -> str:
    parts = [idea.get("title", ""), idea.get("description", ""),
             idea.get("keywords", "")]
    for v in (idea_dna or {}).values():
        parts.append(" ".join(v) if isinstance(v, list) else str(v))
    return " ".join(parts)


def _fallback_chart(idea: dict, idea_dna: dict, patent: dict) -> List[dict]:
    elements = split_claim_elements(patent.get("representative_claim", ""))
    corpus_tokens = set(tokenize(_idea_corpus(idea, idea_dna)))
    rows = []
    for el in elements:
        el_tokens = set(tokenize(el))
        sim = jaccard(el_tokens, corpus_tokens)
        overlap = el_tokens & corpus_tokens
        if sim >= 0.25 or len(overlap) >= 3:
            verdict, comment = "일치 가능", \
                f"내 아이디어에 유사 구성 존재 ({', '.join(list(overlap)[:4])})"
        elif overlap:
            verdict, comment = "부분", \
                f"일부 요소만 겹침 ({', '.join(list(overlap)[:3])})"
        else:
            verdict, comment = "차이", "내 아이디어에서 대응 구성 미확인 — 차별 포인트 후보"
        rows.append({"특허 구성요소": el, "내 아이디어 대응": verdict,
                     "코멘트": comment})
    if not rows:
        rows.append({"특허 구성요소": "(대표청구항 정보 부족)",
                     "내 아이디어 대응": "-", "코멘트": "청구항 원문 확인 필요"})
    return rows


def build_claim_chart(idea: dict, idea_dna: dict, patent: dict) -> tuple:
    """청구항 대비표 생성. (행 리스트, 방법 'gemini'|'fallback') 반환."""
    if gemini_service.is_available():
        prompt = f"""내 아이디어와 아래 특허의 대표청구항을 구성요소 단위로 비교한
청구항 대비표를 만드세요. 침해/유효성을 단정하지 말고 '일치 가능/부분/차이'로만
표기하세요.

내 아이디어: {idea.get('title','')}
설명: {idea.get('description','')}
아이디어 DNA: {json.dumps(idea_dna, ensure_ascii=False)}

특허명: {patent.get('title','')}
대표청구항: {patent.get('representative_claim','')}

반드시 아래 JSON 배열로만 응답하세요.
[{{"특허 구성요소":"청구항을 구성요소로 분해한 항목",
   "내 아이디어 대응":"일치 가능|부분|차이",
   "코멘트":"근거 한 줄"}}]"""
        result = gemini_service.generate_json(prompt)
        if isinstance(result, list) and result:
            rows = []
            for r in result[:14]:
                if isinstance(r, dict) and r.get("특허 구성요소"):
                    rows.append({
                        "특허 구성요소": str(r.get("특허 구성요소", ""))[:160],
                        "내 아이디어 대응": str(r.get("내 아이디어 대응", "-")),
                        "코멘트": str(r.get("코멘트", ""))[:160]})
            if rows:
                return rows, "gemini"
    return _fallback_chart(idea, idea_dna, patent), "fallback"


def summary(rows: List[dict]) -> dict:
    """대비표 요약 카운트."""
    c = {"일치 가능": 0, "부분": 0, "차이": 0}
    for r in rows:
        v = r.get("내 아이디어 대응", "")
        for k in c:
            if k in v:
                c[k] += 1
                break
    return c
