# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 특허 DNA 추출 및 비교."""
from typing import List

from services import gemini_service
from utils.text_utils import jaccard, tokenize

DNA_FIELDS = [
    ("target", "대상"),
    ("problem", "문제"),
    ("solution", "해결수단"),
    ("components", "구성요소"),
    ("stage", "적용시점"),
    ("method", "제조/시공방법"),
    ("effect", "효과"),
]

# DNA 유사도 가중치 (합계 100)
DNA_WEIGHTS = {
    "target": 20, "problem": 15, "solution": 30,
    "components": 15, "stage": 10, "effect": 10,
}

# fallback DNA 추출용 단서 키워드
_PROBLEM_HINTS = ["문제", "단점", "어려움", "곤란", "저하", "누수", "균열", "지연"]
_EFFECT_HINTS = ["효과", "향상", "단축", "절감", "방지", "확보", "개선", "증대"]
_METHOD_HINTS = ["방법", "공법", "단계", "공정", "제조", "시공"]


def _fallback_dna(title: str, abstract: str, claim: str) -> dict:
    """Gemini 실패 시 키워드 기반 기본 DNA."""
    title_tokens = tokenize(title)
    abstract_sents = [s.strip() for s in str(abstract).split(".") if s.strip()]

    def find_sentence(hints):
        for sent in abstract_sents:
            if any(h in sent for h in hints):
                return sent[:120]
        return ""

    claim_tokens = tokenize(claim)
    components = list(dict.fromkeys(claim_tokens))[:8]

    from analyzers.classifier import classify_text
    return {
        "target": " ".join(title_tokens[:3]),
        "problem": find_sentence(_PROBLEM_HINTS),
        "solution": abstract_sents[0][:120] if abstract_sents else title,
        "components": components,
        "stage": "시공" if "시공" in (title + abstract) else
                 ("생산" if any(h in (title + abstract) for h in ("제조", "생산", "제작")) else ""),
        "method": find_sentence(_METHOD_HINTS),
        "effect": find_sentence(_EFFECT_HINTS),
        "technology_group": classify_text(f"{title} {abstract}"),
    }


def extract_dna(patent: dict, use_gemini: bool = True) -> dict:
    """특허 1건의 DNA 추출. Gemini 실패 시 fallback."""
    title = str(patent.get("title", ""))
    abstract = str(patent.get("abstract", ""))
    claim = str(patent.get("representative_claim", ""))
    if use_gemini and gemini_service.is_available():
        dna = gemini_service.extract_patent_dna(title, abstract, claim)
        if dna and isinstance(dna, dict) and dna.get("target"):
            dna.setdefault("components", [])
            return dna
    return _fallback_dna(title, abstract, claim)


def _field_text(value) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value or "")


def field_similarity(a, b) -> float:
    """DNA 한 항목의 일치도 (0~1). 토큰 자카드 + 부분포함 보정."""
    ta, tb = tokenize(_field_text(a)), tokenize(_field_text(b))
    if not ta or not tb:
        return 0.0
    base = jaccard(ta, tb)
    # 부분 문자열 매칭 보너스 (한국어 복합어 대응)
    partial = sum(1 for x in set(ta) for y in set(tb)
                  if x != y and (x in y or y in x))
    bonus = min(partial * 0.05, 0.3)
    return min(base + bonus, 1.0)


def dna_similarity(idea_dna: dict, patent_dna: dict) -> float:
    """가중치 적용 DNA 유사도 (0~100)."""
    if not idea_dna or not patent_dna:
        return 0.0
    total = 0.0
    for field, weight in DNA_WEIGHTS.items():
        total += field_similarity(idea_dna.get(field), patent_dna.get(field)) * weight
    return round(total, 1)


def compare_table(idea_dna: dict, patent_dna: dict,
                  drawing_caption: str = "") -> List[dict]:
    """Patent DNA 화면용 비교표 행 생성."""
    rows = []
    for field, label in DNA_FIELDS:
        a = _field_text(idea_dna.get(field))
        b = _field_text(patent_dna.get(field))
        sim = round(field_similarity(a, b) * 100)
        if sim >= 60:
            comment = "구성이 상당히 유사함 — 청구항 대비 검토 필요"
        elif sim >= 30:
            comment = "부분적으로 겹침 — 차별 포인트 확인 권장"
        elif a and b:
            comment = "차이가 큼 — 차별화 근거로 활용 가능"
        else:
            comment = "비교 정보 부족"
        rows.append({
            "구분": label,
            "내 아이디어": a or "-",
            "선택 특허": b or "-",
            "일치도(%)": sim,
            "코멘트": comment,
        })
    rows.append({
        "구분": "도면상 특징",
        "내 아이디어": "-",
        "선택 특허": drawing_caption or "-",
        "일치도(%)": 0,
        "코멘트": "도면 직접 확인 필요",
    })
    return rows


def common_and_diff(idea_dna: dict, patent_dna: dict) -> tuple:
    """공통점/차이점 토큰 목록."""
    idea_tokens = set()
    pat_tokens = set()
    for field, _ in DNA_FIELDS:
        idea_tokens |= set(tokenize(_field_text(idea_dna.get(field))))
        pat_tokens |= set(tokenize(_field_text(patent_dna.get(field))))
    common = sorted(idea_tokens & pat_tokens)
    diff = sorted(idea_tokens - pat_tokens)
    return common[:15], diff[:15]
