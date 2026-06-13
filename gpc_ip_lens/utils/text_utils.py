# -*- coding: utf-8 -*-
"""GPC IP Lens - 한국어/영문 혼합 특허 텍스트 처리 유틸."""
import re
from collections import Counter
from typing import Iterable, List

# 특허 문서에서 의미가 약한 불용어 (조사/형식어 위주)
STOPWORDS = {
    "및", "또는", "있는", "위한", "하는", "되는", "상기", "그", "이", "을", "를",
    "은", "는", "가", "에", "의", "와", "과", "으로", "로", "에서", "에게", "이를",
    "특징으로", "관한", "것을", "것이다", "한다", "이다", "포함하는", "구비하는",
    "있어서", "청구항", "발명은", "발명의", "본", "수", "것", "등", "중", "내",
    "있다", "한다", "된다", "효과가", "위하여", "따라", "의해", "통해", "대한",
    "단계와", "단계를", "포함한다", "형성된", "형성되", "구비한",
    "the", "a", "an", "of", "and", "or", "for", "in", "on", "to", "with",
    "method", "system", "apparatus",
}

_TOKEN_RE = re.compile(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]+[A-Za-z가-힣]+")


def tokenize(text: str) -> List[str]:
    """한글/영문 토큰 추출 (간이 형태소 분석 대용)."""
    if not text:
        return []
    tokens = _TOKEN_RE.findall(str(text))
    out = []
    for t in tokens:
        t = t.strip().lower()
        if t in STOPWORDS or len(t) < 2:
            continue
        # 한국어 조사 꼬리 간이 제거 (예: "기둥의" -> "기둥")
        if re.match(r"^[가-힣]+$", t) and len(t) >= 3 and t[-1] in "의를을은는이가와과로":
            stem = t[:-1]
            if len(stem) >= 2:
                t = stem
        if t not in STOPWORDS:
            out.append(t)
    return out


def keyword_counts(texts: Iterable[str], top_n: int = 20) -> List[tuple]:
    """여러 텍스트에서 키워드 빈도 TOP N."""
    counter = Counter()
    for text in texts:
        counter.update(set(tokenize(text)))
    return counter.most_common(top_n)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """0~1 자카드 유사도."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def overlap_ratio(query_tokens: Iterable[str], doc_tokens: Iterable[str]) -> float:
    """질의 토큰 중 문서에 등장하는 비율 (0~1)."""
    sq, sd = set(query_tokens), set(doc_tokens)
    if not sq:
        return 0.0
    return len(sq & sd) / len(sq)


def split_keywords(raw: str) -> List[str]:
    """쉼표/줄바꿈 구분 키워드 문자열을 리스트로."""
    if not raw:
        return []
    parts = re.split(r"[,\n;/]+", str(raw))
    return [p.strip() for p in parts if p.strip()]
