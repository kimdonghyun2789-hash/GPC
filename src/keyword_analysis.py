"""아이디어 문장에서 핵심 키워드와 검색어 후보를 만든다."""
from collections import Counter

from src import synonyms
from src.utils import tokenize


def extract_keywords(text: str, max_keywords: int = 8) -> list:
    """빈도와 등장 순서를 기준으로 핵심 키워드를 추출한다."""
    tokens = tokenize(text)
    if not tokens:
        return []
    counts = Counter(tokens)
    first_seen = {}
    for index, token in enumerate(tokens):
        first_seen.setdefault(token, index)
    ordered = sorted(counts, key=lambda t: (-counts[t], first_seen[t]))
    return ordered[:max_keywords]


def _dedupe(queries: list) -> list:
    seen = set()
    unique = []
    for query in queries:
        if query and query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def build_search_queries(keywords: list) -> list:
    """KIPRIS 검색에 사용할 검색어 후보를 우선순위 순으로 생성한다.

    '*' 는 AND 결합이며, 좁은 검색부터 넓은 검색 순으로 시도한다.
    동의어 사전에 등록된 표기 차이(예: 프리캐스트/PC)도 후보에 포함한다.
    """
    queries = []
    if len(keywords) >= 2:
        queries.append(f"{keywords[0]}*{keywords[1]}")
        # 동의어 표기로 같은 조합을 추가 (각 1개씩만)
        for alt in synonyms.expand_term(keywords[0])[1:2]:
            if alt != keywords[0]:
                queries.append(f"{alt}*{keywords[1]}")
        for alt in synonyms.expand_term(keywords[1])[1:2]:
            if alt != keywords[1]:
                queries.append(f"{keywords[0]}*{alt}")
    if len(keywords) >= 3:
        queries.append(f"{keywords[0]}*{keywords[2]}")
        queries.append(f"{keywords[1]}*{keywords[2]}")
    if keywords:
        queries.append(keywords[0])
    if len(keywords) >= 2:
        queries.append(keywords[1])
    return _dedupe(queries)


def build_foreign_queries(keywords: list) -> list:
    """해외 검색용 후보 — 동의어 사전의 영문 표기를 우선 사용한다."""
    english = [synonyms.english_synonym(k) or k for k in keywords]
    queries = []
    if len(english) >= 2:
        queries.append(f"{english[0]}*{english[1]}")
    if len(english) >= 3:
        queries.append(f"{english[0]}*{english[2]}")
        queries.append(f"{english[1]}*{english[2]}")
    if english:
        queries.append(english[0])
    if len(english) >= 2:
        queries.append(english[1])
    return _dedupe(queries)
