"""아이디어와 검색된 특허 간 유사도 분석.

분석 기준: 제목 유사도, 요약 유사도, 청구항 유사도,
핵심 키워드 일치도, IPC/CPC 일치 여부.

유사도는 TF-IDF 가중 코사인 방식이다 — 검색 결과 전체를 모집단으로
흔한 단어(구조, 콘크리트 등)의 비중을 낮추고 희소한 핵심 용어에
가중치를 둔다. 토큰은 동의어 사전의 대표어로 정규화해 비교한다.
"""
import math
from collections import Counter

from src import synonyms
from src.utils import overlap_ratio, token_set, tokenize


def _canonical_list(text) -> list:
    return synonyms.canonicalize_list(tokenize(text))


def _canonical_set(text) -> set:
    return synonyms.canonicalize_tokens(token_set(text))


# ---------------------------------------------------------------------------
# TF-IDF
# ---------------------------------------------------------------------------
def _build_idf(documents: list) -> dict:
    """문서(토큰 리스트) 목록으로 IDF 표를 만든다."""
    total = len(documents)
    df = Counter()
    for tokens in documents:
        df.update(set(tokens))
    return {
        token: math.log((1 + total) / (1 + count)) + 1.0
        for token, count in df.items()
    }


def _vectorize(tokens: list, idf: dict) -> dict:
    counts = Counter(tokens)
    return {
        token: (1.0 + math.log(count)) * idf.get(token, 1.0)
        for token, count in counts.items()
    }


def _cosine(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    if len(b) < len(a):
        a, b = b, a
    dot = sum(weight * b.get(token, 0.0) for token, weight in a.items())
    if dot == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(w * w for w in a.values()))
    norm_b = math.sqrt(sum(w * w for w in b.values()))
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# 등급/사유
# ---------------------------------------------------------------------------
def _ipc_main_class(ipc: str) -> str:
    """IPC 문자열에서 메인 클래스(예: E04B)만 추출한다."""
    code = str(ipc or "").strip()
    return code[:4].upper().replace(" ", "") if code else ""


def _dominant_ipc_classes(patents: list, top: int = 3) -> set:
    counter = Counter(
        _ipc_main_class(p.get("ipc")) for p in patents if _ipc_main_class(p.get("ipc"))
    )
    # 1건뿐인 분류는 주류로 보지 않는다
    return {code for code, count in counter.most_common(top) if count >= 2}


def _grade(score: float) -> str:
    if score >= 0.55:
        return "매우 유사"
    if score >= 0.35:
        return "유사"
    if score >= 0.15:
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


# ---------------------------------------------------------------------------
# 분석
# ---------------------------------------------------------------------------
def analyze(idea_text: str, keywords: list, patents: list, top_n: int) -> list:
    """유사도 점수 상위 top_n 건을 순위와 함께 반환한다."""
    idea_tokens = _canonical_list(idea_text)

    # 키워드별 대표어 매핑 (표시는 원래 키워드로, 비교는 대표어로)
    keyword_canonical = {k: synonyms.canonicalize(k) for k in keywords}
    keyword_tokens = set(keyword_canonical.values())
    canonical_to_keyword = {}
    for keyword, canonical in keyword_canonical.items():
        canonical_to_keyword.setdefault(canonical, keyword)

    dominant_ipc = _dominant_ipc_classes(patents)

    # 특허별 필드 토큰을 만들고, 전체 문서 기준 IDF를 계산한다.
    field_tokens = []
    for patent in patents:
        title = _canonical_list(patent.get("title"))
        abstract = _canonical_list(patent.get("abstract"))
        claims = _canonical_list(patent.get("claims"))
        field_tokens.append((title, abstract, claims))
    idf = _build_idf([t + a + c for t, a, c in field_tokens] + [idea_tokens])
    idea_vector = _vectorize(idea_tokens, idf)

    scored = []
    for patent, (title, abstract, claims) in zip(patents, field_tokens):
        title_sim = _cosine(idea_vector, _vectorize(title, idf))
        abstract_sim = _cosine(idea_vector, _vectorize(abstract, idf))
        claims_sim = _cosine(idea_vector, _vectorize(claims, idf))

        text_tokens = set(title) | set(abstract) | set(claims)
        keyword_match = overlap_ratio(keyword_tokens, text_tokens)
        ipc_match = 1.0 if _ipc_main_class(patent.get("ipc")) in dominant_ipc else 0.0

        if claims:
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

        matched_canonical = keyword_tokens & text_tokens
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
                "review_reason": _review_reason(grade, matched_keywords, bool(claims)),
            }
        )
        scored.append(enriched)

    scored.sort(key=lambda p: p["score"], reverse=True)
    top = scored[:top_n]
    for rank, patent in enumerate(top, start=1):
        patent["rank"] = rank
    return top
