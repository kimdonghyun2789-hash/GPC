# -*- coding: utf-8 -*-
"""GPC IP Lens - 검색어 확장 (Gemini + fallback)."""
from typing import List

from services import gemini_service
from utils.text_utils import split_keywords, tokenize

# 건설/PC 도메인 동의어 사전 (fallback 용)
DOMAIN_SYNONYMS = {
    "pc": ["프리캐스트", "precast", "PC부재"],
    "프리캐스트": ["PC", "precast", "기성콘크리트"],
    "기둥": ["column", "주각", "중공기둥"],
    "중공": ["hollow", "중공부", "중공기둥"],
    "접합": ["접합부", "이음", "조인트", "joint", "connection"],
    "전단키": ["shear key", "전단연결재", "전단돌기"],
    "배수": ["drain", "배수구", "배수관", "drainage"],
    "방수": ["waterproof", "지수", "차수"],
    "몰드": ["mold", "거푸집", "형틀", "form"],
    "슬리브": ["sleeve", "선매립", "커플러"],
    "생산": ["제조", "제작", "production", "manufacturing"],
    "유지관리": ["maintenance", "점검", "보수"],
    "품질관리": ["quality", "QC", "검사"],
    "센서": ["sensor", "계측", "모니터링"],
    "더블월": ["double wall", "이중벽", "중공벽"],
    "벽체": ["wall", "월", "패널"],
}

EMPTY_EXPANSION = {
    "korean_keywords": [], "english_keywords": [], "synonyms": [],
    "exclude_keywords": [], "search_queries": [], "technology_groups": [],
    "idea_dna": {"target": "", "problem": "", "solution": "",
                 "components": [], "stage": "", "method": "", "effect": "",
                 "technology_group": ""},
}


def fallback_expand(idea_title: str, idea_description: str,
                    keywords: str, exclude_keywords: str) -> dict:
    """Gemini 실패/미설정 시 키워드 기반 fallback 검색어 확장."""
    user_keywords = split_keywords(keywords)
    desc_tokens = tokenize(f"{idea_title} {idea_description}")
    base = list(dict.fromkeys(user_keywords + desc_tokens))[:12]

    synonyms: List[str] = []
    english: List[str] = []
    for kw in base:
        for key, syns in DOMAIN_SYNONYMS.items():
            if key in kw.lower():
                for s in syns:
                    if s.isascii():
                        english.append(s)
                    else:
                        synonyms.append(s)
    synonyms = list(dict.fromkeys(synonyms))[:10]
    english = list(dict.fromkeys(english))[:10]

    # 검색식 후보: 핵심 키워드 2~3개 조합
    queries: List[str] = []
    if len(base) >= 2:
        queries.append("*".join(base[:2]))
    if len(base) >= 3:
        queries.append("*".join(base[:3]))
        queries.append(f"{base[0]}*{base[2]}")
    if base:
        queries.append(base[0])
        for s in synonyms[:2]:
            queries.append(f"{base[0]}*{s}")
    queries = list(dict.fromkeys(queries))[:5]

    from analyzers.classifier import classify_text
    tech_group = classify_text(f"{idea_title} {idea_description} {keywords}")

    result = dict(EMPTY_EXPANSION)
    result.update({
        "korean_keywords": [k for k in base if not k.isascii()],
        "english_keywords": english,
        "synonyms": synonyms,
        "exclude_keywords": split_keywords(exclude_keywords),
        "search_queries": queries,
        "technology_groups": [tech_group],
        "idea_dna": {
            "target": base[0] if base else "",
            "problem": "",
            "solution": " ".join(base[1:3]),
            "components": base[:5],
            "stage": "",
            "method": "",
            "effect": "",
            "technology_group": tech_group,
        },
    })
    return result


def expand(idea_title: str, idea_description: str,
           keywords: str, exclude_keywords: str) -> tuple:
    """검색어 확장 실행. (결과 dict, 사용한 방법 'gemini'|'fallback') 반환."""
    result = None
    if gemini_service.is_available():
        result = gemini_service.expand_keywords(
            idea_title, idea_description, keywords, exclude_keywords)
    if result and isinstance(result, dict) and result.get("search_queries"):
        # 누락 필드 보정
        merged = dict(EMPTY_EXPANSION)
        merged.update(result)
        merged.setdefault("idea_dna", EMPTY_EXPANSION["idea_dna"])
        return merged, "gemini"
    return fallback_expand(idea_title, idea_description,
                           keywords, exclude_keywords), "fallback"
