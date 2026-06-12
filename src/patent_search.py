"""검색 범위(국내/해외/국내+해외)에 따라 특허 검색을 실행하고 결과를 합친다."""
from src.patent_sources import kipris_source
from src.patent_sources.kipris_source import PatentSearchError  # noqa: F401

# 유사도 분석 모수를 확보하기 위한 1회 검색당 최대 수집 건수
MAX_COLLECT = 200
ROWS_PER_QUERY = 100


def _dedupe(patents: list) -> list:
    seen = set()
    unique = []
    for patent in patents:
        key = (
            patent.get("pub_number")
            or patent.get("app_number")
            or patent.get("title")
        )
        if key and key not in seen:
            seen.add(key)
            unique.append(patent)
    return unique


def _search_one_scope(search_fn, queries: list) -> tuple:
    """검색어 후보를 좁은 것부터 시도해 충분한 결과를 모은다."""
    collected = []
    used_queries = []
    last_error = None
    for query in queries:
        try:
            results = search_fn(query, rows=ROWS_PER_QUERY)
        except PatentSearchError as exc:
            last_error = exc
            continue
        if results:
            used_queries.append(query)
            collected.extend(results)
        if len(_dedupe(collected)) >= MAX_COLLECT:
            break
    if not collected and last_error is not None:
        raise last_error
    return _dedupe(collected)[:MAX_COLLECT], used_queries


def run_search(scope: str, queries: list, foreign_queries: list = None) -> dict:
    """범위별 검색 실행. 반환: {"patents": [...], "used_queries": [...]}

    해외 검색은 foreign_queries(영문 표기 우선)가 주어지면 그것을 사용한다.
    국내+해외 검색은 한쪽이 실패해도 다른 쪽 결과는 살리고,
    양쪽 모두 실패한 경우에만 오류를 올린다.
    """
    patents = []
    used_queries = []
    errors = []

    search_plans = []
    if scope in ("국내특허", "국내+해외"):
        search_plans.append((kipris_source.search_kr, queries))
    if scope in ("해외특허", "국내+해외"):
        search_plans.append(
            (kipris_source.search_foreign, foreign_queries or queries)
        )

    for search_fn, scope_query_list in search_plans:
        try:
            scope_patents, scope_queries = _search_one_scope(
                search_fn, scope_query_list
            )
        except PatentSearchError as exc:
            errors.append(exc)
            continue
        patents.extend(scope_patents)
        used_queries.extend(q for q in scope_queries if q not in used_queries)

    if not patents and errors:
        detail = " / ".join(error.detail for error in errors if error.detail)
        raise PatentSearchError(str(errors[0]), detail=detail)

    return {"patents": _dedupe(patents), "used_queries": used_queries}
