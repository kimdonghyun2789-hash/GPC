# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 구성요소 매칭표 (Element Matching).

내 아이디어를 핵심 구성요소로 분해하고, 유사특허의 대표청구항/요약과 비교해
일치/부분일치/차이/미확인을 판정한다. 규칙 기반으로 동작하며 Gemini 가 있으면
더 정교한 분해/판정을 시도한다. (변리사 검토 전 1차 참고 자료)
"""
import json
import re
from typing import List

from services import gemini_service
from utils.text_utils import jaccard, split_keywords, tokenize

VERDICTS = ["일치", "부분일치", "차이", "미확인"]


def decompose_idea(idea: dict, idea_dna: dict) -> List[str]:
    """아이디어를 핵심 구성요소 리스트로 분해 (규칙 기반)."""
    elems: List[str] = []
    dna = idea_dna or {}
    # 1) DNA 구성요소 우선
    comp = dna.get("components")
    if isinstance(comp, list):
        elems += [str(c).strip() for c in comp if str(c).strip()]
    # 2) 핵심 키워드
    elems += split_keywords(idea.get("keywords", ""))
    # 3) 설명에서 명사구 후보(2~4 토큰 연속) 일부
    desc = str(idea.get("description", ""))
    for sent in re.split(r"[.,\n]", desc):
        toks = tokenize(sent)
        if 2 <= len(toks) <= 6:
            elems.append(" ".join(toks[:4]))
    # 정리: 중복 제거 + 너무 짧은 것 제거 + 상위 N
    seen, out = set(), []
    for e in elems:
        e = e.strip()
        key = e.replace(" ", "")
        if len(key) >= 2 and key not in seen:
            seen.add(key)
            out.append(e)
    return out[:8]


def _evidence_sentence(patent: dict, el_tokens: set) -> str:
    """청구항/요약에서 element 토큰이 가장 많이 겹치는 문장을 근거로."""
    text = " ".join([str(patent.get("representative_claim", "")),
                     str(patent.get("abstract", ""))])
    best, best_hit = "", 0
    for sent in re.split(r"[.\n]", text):
        st = set(tokenize(sent))
        hit = len(el_tokens & st)
        if hit > best_hit:
            best_hit, best = hit, sent.strip()
    return best[:140]


def _fallback_match(idea_elements: List[str], patent: dict) -> List[dict]:
    claim = str(patent.get("representative_claim", ""))
    abstract = str(patent.get("abstract", ""))
    title = str(patent.get("title", ""))
    has_claim = bool(claim.strip())
    claim_tokens = set(tokenize(claim))
    doc_tokens = set(tokenize(f"{title} {abstract} {claim}"))
    rows = []
    for el in idea_elements:
        et = set(tokenize(el))
        if not et:
            continue
        in_claim = len(et & claim_tokens)
        in_doc = len(et & doc_tokens)
        jc = jaccard(et, claim_tokens) if has_claim else 0.0
        if not has_claim:
            verdict = "미확인"
        elif in_claim >= max(1, len(et)) and jc >= 0.2:
            verdict = "일치"
        elif in_claim >= 1:
            verdict = "부분일치"
        elif in_doc >= 1:
            verdict = "부분일치"
        else:
            verdict = "차이"
        diff = "높음" if verdict in ("차이", "미확인") else (
            "보통" if verdict == "부분일치" else "낮음")
        rows.append({
            "내 아이디어 구성요소": el,
            "유사특허 청구항 구성": _evidence_sentence(patent, et) or "-",
            "일치 여부": verdict,
            "근거 청구항": "대표청구항" if in_claim else ("요약" if in_doc else "-"),
            "차별화 가능성": diff,
        })
    return rows


def match(idea: dict, idea_dna: dict, patent: dict,
          idea_elements: List[str] = None) -> tuple:
    """구성요소 매칭표 생성. (행 리스트, 방법 'gemini'|'fallback') 반환."""
    els = idea_elements or decompose_idea(idea, idea_dna)
    if gemini_service.is_available():
        prompt = f"""당신은 건설/PC 분야 특허 분석 보조도구입니다.
내 아이디어의 핵심 구성요소가 아래 특허의 대표청구항에 존재하는지 비교하세요.
침해/유효성을 단정하지 말고 일치/부분일치/차이/미확인으로만 판정하세요.

내 아이디어 구성요소: {json.dumps(els, ensure_ascii=False)}
특허명: {patent.get('title','')}
대표청구항: {patent.get('representative_claim','')}
요약: {patent.get('abstract','')}

아래 JSON 배열로만 응답:
[{{"내 아이디어 구성요소":"...","유사특허 청구항 구성":"근거 문장",
   "일치 여부":"일치|부분일치|차이|미확인","근거 청구항":"청구항 번호/위치",
   "차별화 가능성":"높음|보통|낮음"}}]"""
        res = gemini_service.generate_json(prompt)
        if isinstance(res, list) and res:
            rows = [r for r in res if isinstance(r, dict)
                    and r.get("내 아이디어 구성요소")]
            if rows:
                return rows[:12], "gemini"
    return _fallback_match(els, patent), "fallback"


def summary(rows: List[dict]) -> dict:
    c = {v: 0 for v in VERDICTS}
    for r in rows:
        v = r.get("일치 여부", "")
        for k in VERDICTS:
            if k in v:
                c[k] += 1
                break
    return c
