"""아이디어 문장에서 핵심 키워드와 검색어 후보를 만든다."""
from collections import Counter

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


def build_search_queries(keywords: list) -> list:
    """KIPRIS 검색에 사용할 검색어 후보를 우선순위 순으로 생성한다.

    '*' 는 AND 결합이며, 좁은 검색부터 넓은 검색 순으로 시도한다.
    """
    queries = []
    if len(keywords) >= 2:
        queries.append(f"{keywords[0]}*{keywords[1]}")
    if len(keywords) >= 3:
        queries.append(f"{keywords[0]}*{keywords[2]}")
        queries.append(f"{keywords[1]}*{keywords[2]}")
    if keywords:
        queries.append(keywords[0])
    if len(keywords) >= 2:
        queries.append(keywords[1])

    seen = set()
    unique = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique
