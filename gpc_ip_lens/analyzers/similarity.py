# -*- coding: utf-8 -*-
"""GPC IP Lens - 유사도 계산 엔진.

종합 유사도 가중치 (총 100점):
- 벡터 의미 유사도 30 / 특허 DNA 25 / 키워드 20 / 대표청구항 15
- IPC/CPC 일치 5 / Gemini 위험도 보정 5
"""
from typing import List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from analyzers import patent_dna as dna_mod
from services import gemini_service
from utils.text_utils import split_keywords, tokenize

TOTAL_WEIGHTS = {
    "vector": 0.30, "dna": 0.25, "keyword": 0.20,
    "claim": 0.15, "ipc": 0.05, "ai_risk": 0.05,
}

# 기술군 → 관련 IPC 메인클래스 (IPC 일치 점수용)
GROUP_IPC = {
    "접합부": ["E04B", "E04C", "E01D"],
    "전단키": ["E04B", "E04C"],
    "생산방법": ["B28B", "E04C"],
    "몰드": ["B28B", "E04G"],
    "배수": ["E03F", "E04D", "E02D"],
    "방수": ["E04D", "E04B"],
    "품질관리": ["G01N", "G01M"],
    "유지관리": ["E04G", "G01M"],
    "센서": ["G01D", "G08C", "G01N"],
    "시공장비": ["E04G", "B66C"],
    "기타": ["E04B", "E04C"],
}


def build_patent_text(p: dict) -> str:
    """특허 비교 텍스트: 특허명+요약+대표청구항+IPC/CPC+키워드."""
    parts = [
        str(p.get("title", "")), str(p.get("abstract", "")),
        str(p.get("representative_claim", "")),
        str(p.get("ipc", "")), str(p.get("cpc", "")),
    ]
    text = " ".join(parts)
    top_tokens = " ".join(tokenize(text)[:30])
    return f"{text} {top_tokens}"


def build_idea_text(title: str, description: str, idea_dna: dict,
                    expanded_keywords: List[str]) -> str:
    """아이디어 비교 텍스트: 아이디어명+설명+DNA+확장 키워드."""
    dna_text = " ".join(
        dna_mod._field_text(idea_dna.get(f)) for f, _ in dna_mod.DNA_FIELDS
    ) if idea_dna else ""
    return f"{title} {description} {dna_text} {' '.join(expanded_keywords or [])}"


# ----------------------------------------------------------- 벡터 유사도
def _cosine_to_score(value: float) -> float:
    """cosine(-1~1) → 0~100. 음수는 0 처리."""
    return round(max(0.0, min(1.0, float(value))) * 100, 1)


def vector_scores(idea_text: str, patent_texts: List[str],
                  try_gemini: bool = True) -> tuple:
    """아이디어 vs 각 특허 벡터 유사도 (0~100 리스트, 방법명).

    1순위 Gemini embedding → 실패 시 TF-IDF cosine fallback.
    한국어 복합어 대응을 위해 문자 n-gram TF-IDF 를 사용한다.
    """
    if not patent_texts:
        return [], "none"
    if try_gemini and gemini_service.is_available():
        embeddings = gemini_service.embed_texts([idea_text] + patent_texts)
        if embeddings:
            mat = np.array(embeddings)
            sims = cosine_similarity(mat[:1], mat[1:])[0]
            return [_cosine_to_score(s) for s in sims], "gemini-embedding"
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                                 max_features=20000)
    matrix = vectorizer.fit_transform([idea_text] + patent_texts)
    sims = cosine_similarity(matrix[0:1], matrix[1:])[0]
    return [_cosine_to_score(s) for s in sims], "tfidf"


def pairwise_vector_matrix(texts: List[str]) -> np.ndarray:
    """특허 간 벡터 유사도 행렬 (0~1). 네트워크맵 엣지용."""
    if len(texts) < 2:
        return np.zeros((len(texts), len(texts)))
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                                 max_features=20000)
    matrix = vectorizer.fit_transform(texts)
    return cosine_similarity(matrix)


# ----------------------------------------------------------- 키워드 유사도
def keyword_score(idea_keywords: List[str], patent: dict) -> tuple:
    """키워드 일치도 (0~100, 일치 키워드 목록).

    반영: 제목 일치(가중 3) / 요약 일치(2) / 청구항 일치(2) / 동시출현(1)
    """
    kws = [k.lower() for k in idea_keywords if k]
    if not kws:
        return 0.0, []
    title = str(patent.get("title", "")).lower()
    abstract = str(patent.get("abstract", "")).lower()
    claim = str(patent.get("representative_claim", "")).lower()

    matched = set()
    score = 0.0
    max_per_kw = 3 + 2 + 2 + 1
    for kw in kws:
        s = 0
        if kw in title:
            s += 3
        if kw in abstract:
            s += 2
        if kw in claim:
            s += 2
        # 동시출현: 두 영역 이상에서 등장
        if sum(kw in t for t in (title, abstract, claim)) >= 2:
            s += 1
        if s > 0:
            matched.add(kw)
        score += s
    normalized = score / (len(kws) * max_per_kw) * 100
    return round(min(normalized * 1.5, 100), 1), sorted(matched)


# ----------------------------------------------------------- 청구항 유사도
def claim_scores(idea_text: str, claims: List[str]) -> List[float]:
    """아이디어 vs 대표청구항 TF-IDF cosine (0~100)."""
    if not claims:
        return []
    safe = [c if str(c).strip() else "없음" for c in claims]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                                 max_features=20000)
    matrix = vectorizer.fit_transform([idea_text] + safe)
    sims = cosine_similarity(matrix[0:1], matrix[1:])[0]
    return [_cosine_to_score(s) for s in sims]


# ------------------------------------------------------------- IPC 일치
def ipc_score(idea_groups: List[str], patent_ipc: str) -> float:
    """아이디어 기술군과 특허 IPC 메인클래스 일치 (0~100)."""
    if not patent_ipc:
        return 0.0
    wanted = set()
    for g in idea_groups or ["기타"]:
        wanted.update(GROUP_IPC.get(g, []))
    pat_classes = {c.strip()[:4].upper() for c in str(patent_ipc).split(",") if c.strip()}
    if not wanted or not pat_classes:
        return 0.0
    return 100.0 if wanted & pat_classes else 0.0


# ------------------------------------------------------------- 종합 점수
def total_score(vector: float, dna: float, keyword: float,
                claim: float, ipc: float, ai_risk: Optional[float] = None) -> float:
    """가중합 종합 유사도 (0~100). ai_risk 미산출 시 나머지 평균으로 보정."""
    if ai_risk is None:
        ai_risk = (vector + dna + keyword + claim) / 4
    score = (vector * TOTAL_WEIGHTS["vector"] + dna * TOTAL_WEIGHTS["dna"]
             + keyword * TOTAL_WEIGHTS["keyword"] + claim * TOTAL_WEIGHTS["claim"]
             + ipc * TOTAL_WEIGHTS["ipc"] + ai_risk * TOTAL_WEIGHTS["ai_risk"])
    return round(min(score, 100), 1)


def grade(score: float) -> str:
    """유사도 등급."""
    if score >= 80:
        return "고유사/주의"
    if score >= 60:
        return "유사"
    if score >= 40:
        return "관련 있음"
    return "낮음"


def risk_emoji(score: float) -> str:
    if score >= 80:
        return "🔴"
    if score >= 60:
        return "🟠"
    if score >= 40:
        return "🟡"
    return "🟢"


# ------------------------------------------------------------ 전체 파이프라인
def score_patents(idea: dict, patents: List[dict],
                  expansion: dict, use_gemini_dna: bool = False) -> List[dict]:
    """검색 결과 전체에 대해 유사도 일괄 계산.

    idea: {title, description, keywords, idea_dna}
    expansion: keyword_expander 결과 dict
    반환: 각 특허 dict 에 점수 필드가 추가된 리스트 (total_score 내림차순)
    """
    from analyzers.classifier import classify_patent

    if not patents:
        return []

    expanded_keywords = (
        split_keywords(idea.get("keywords", ""))
        + list(expansion.get("korean_keywords", []))
        + list(expansion.get("english_keywords", []))
        + list(expansion.get("synonyms", []))
    )
    expanded_keywords = list(dict.fromkeys(k for k in expanded_keywords if k))
    idea_dna = idea.get("idea_dna") or expansion.get("idea_dna") or {}
    idea_text = build_idea_text(idea.get("title", ""),
                                idea.get("description", ""),
                                idea_dna, expanded_keywords)

    patent_texts = [build_patent_text(p) for p in patents]
    v_scores, v_method = vector_scores(idea_text, patent_texts)
    c_scores = claim_scores(idea_text,
                            [p.get("representative_claim", "") for p in patents])
    idea_groups = expansion.get("technology_groups") or ["기타"]

    results = []
    for i, p in enumerate(patents):
        p = dict(p)
        p_dna = dna_mod.extract_dna(p, use_gemini=use_gemini_dna)
        d_score = dna_mod.dna_similarity(idea_dna, p_dna)
        k_score, matched = keyword_score(expanded_keywords[:15], p)
        i_score = ipc_score(idea_groups, p.get("ipc", ""))
        v_score = v_scores[i] if i < len(v_scores) else 0.0
        cl_score = c_scores[i] if i < len(c_scores) else 0.0
        t_score = total_score(v_score, d_score, k_score, cl_score, i_score)

        p.update({
            "vector_score": v_score,
            "dna_score": d_score,
            "keyword_score": k_score,
            "claim_score": cl_score,
            "ipc_score": i_score,
            "ai_risk_score": round((v_score + d_score + k_score + cl_score) / 4, 1),
            "total_score": t_score,
            "grade": grade(t_score),
            "matched_keywords": matched,
            "patent_dna": p_dna,
            "technology_group": classify_patent(p),
            "vector_method": v_method,
            "comparison_text": patent_texts[i],
        })
        results.append(p)
    results.sort(key=lambda x: x["total_score"], reverse=True)
    for rank, p in enumerate(results, start=1):
        p["rank"] = rank
    return results
