"""아이디어와 검색된 특허 간 유사도 분석.

분석 기준: 제목 유사도, 요약 유사도, 청구항 유사도,
핵심 키워드 일치도, IPC/CPC 일치 여부.
"""
from collections import Counter

from src import synonyms
from src.utils import jaccard, overlap_ratio, token_set


def _canonical_set(text) -> set:
    """동의어를 대표어로 정규화한 토큰 집합 (프리캐스트 = PC 로 취급)."""
    return synonyms.canonicalize_tokens(token_set(text))


def _ipc_main_class(ipc: str) -> str:
    """IPC 문자열에서 메인 클래스(예: E04B)만 추출한다."""
    code = str(ipc or "").strip()
    return code[:4].upper().replace(" ", "") if code else ""


def _dominant_ipc_classes(patents: list, top: int = 3) -> set:
    counter = Counter(
        _ipc_main_class(p.get("ipc")) for p in patents if _ipc_main_class(p.get("ipc"))
    )
    return {code for code, _ in counter.most_common(top)}


def _grade(score: float) -> str:
    if score >= 0.45:
        return "매우 유사"
    if score >= 0.28:
        return "유사"
    if score >= 0.12:
        return "일부 유사"
    return "참고 수준"


def _review_reason(grade: str, matched_keywords: list, has_claims: bool) -> str:
    keywords = ", ".join(matched_keywords[:4]) if matched_keywords else ""
    if grade == "매우 유사":
        base = "핵심 구성과 키워드가 폭넓게 겹쳐 권리범위 중복 가능성 검토가 필요합니다."
    elif grade == "유사":
        base = "주요 키워드가 겹쳐 구성 차이를 확인할 필요가 있습니다."
    elif grade == "일부 유사":
        base = "일부 키워드만 겹치므로 적용 분야 차이를 확인하면 됩니다."
    else:
        base = "관련 분야 참고용으로만 확인하면 됩니다."
    parts = []
    if keywords:
        parts.append(f"일치 키워드: {keywords}.")
    parts.append(base)
    if not has_claims:
        parts.append("청구항 원문은 상세보기에서 원문 열기로 확인이 필요합니다.")
    return " ".join(parts)


def analyze(idea_text: str, keywords: list, patents: list, top_n: int) -> list:
    """유사도 점수 상위 top_n 건을 순위와 함께 반환한다."""
    idea_tokens = _canonical_set(idea_text)
    # 키워드별 대표어 매핑 (표시는 원래 키워드로, 비교는 대표어로)
    keyword_canonical = {
        keyword: next(iter(synonyms.canonicalize_tokens({keyword})))
        for keyword in keywords
    }
    keyword_tokens = set(keyword_canonical.values())
    canonical_to_keyword = {}
    for keyword, canonical in keyword_canonical.items():
        canonical_to_keyword.setdefault(canonical, keyword)
    dominant_ipc = _dominant_ipc_classes(patents)

    scored = []
    for patent in patents:
        title_tokens = _canonical_set(patent.get("title"))
        abstract_tokens = _canonical_set(patent.get("abstract"))
        claims_tokens = _canonical_set(patent.get("claims"))

        title_sim = jaccard(idea_tokens, title_tokens)
        abstract_sim = jaccard(idea_tokens, abstract_tokens)
        claims_sim = jaccard(idea_tokens, claims_tokens)
        keyword_match = overlap_ratio(
            keyword_tokens, title_tokens | abstract_tokens | claims_tokens
        )
        ipc_match = 1.0 if _ipc_main_class(patent.get("ipc")) in dominant_ipc else 0.0

        if claims_tokens:
            score = (
                0.25 * title_sim
                + 0.25 * abstract_sim
                + 0.15 * claims_sim
                + 0.25 * keyword_match
                + 0.10 * ipc_match
            )
        else:
            score = (
                0.30 * title_sim
                + 0.30 * abstract_sim
                + 0.30 * keyword_match
                + 0.10 * ipc_match
            )

        matched_canonical = keyword_tokens & (
            title_tokens | abstract_tokens | claims_tokens
        )
        matched_keywords = sorted(
            (canonical_to_keyword.get(c, c) for c in matched_canonical),
            key=lambda k: keywords.index(k) if k in keywords else 99,
        )
        grade = _grade(score)

        enriched = dict(patent)
        enriched.update(
            {
                "score": round(score, 4),
                "grade": grade,
                "title_sim": round(title_sim, 4),
                "abstract_sim": round(abstract_sim, 4),
                "claims_sim": round(claims_sim, 4),
                "keyword_match": round(keyword_match, 4),
                "ipc_match": "일치" if ipc_match else "불일치",
                "matched_keywords": ", ".join(matched_keywords),
                "review_reason": _review_reason(
                    grade, matched_keywords, bool(claims_tokens)
                ),
            }
        )
        scored.append(enriched)

    scored.sort(key=lambda p: p["score"], reverse=True)
    top = scored[:top_n]
    for rank, patent in enumerate(top, start=1):
        patent["rank"] = rank
    return top
