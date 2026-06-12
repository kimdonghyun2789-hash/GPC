"""재검토 비교와 신규 공개특허 확인.

- 재검토 비교: 같은 아이디어를 다시 검토할 때 이전 검토 대비
  신규 발견 특허와 등급 상승 특허를 알려준다.
- 신규 공개특허 확인: 검토일 이후 새로 공개된 특허가 있는지 확인한다.
"""
from src import ideas, patent_search
from src.keyword_analysis import build_foreign_queries, build_search_queries
from src.similarity import analyze
from src.utils import extract_compact_date, jaccard, token_set

# 아이디어 문장 토큰이 이 비율 이상 겹치면 같은 아이디어의 재검토로 본다
SAME_IDEA_THRESHOLD = 0.5

_GRADE_ORDER = {"매우 유사": 3, "유사": 2, "일부 유사": 1, "참고 수준": 0}


def _patent_key(patent) -> str:
    return (
        str(patent.get("pub_number") or "").strip()
        or str(patent.get("app_number") or "").strip()
        or str(patent.get("title") or "").strip()
    )


def find_previous_idea(idea_text: str, exclude_id: str) -> dict:
    """현재 아이디어와 같은 내용으로 보이는 가장 최근 검토를 찾는다."""
    current_tokens = token_set(idea_text)
    best = {}
    for _, row in ideas.load_ideas().iterrows():
        record = row.to_dict()
        if record.get("idea_id") == exclude_id:
            continue
        similarity = jaccard(current_tokens, token_set(record.get("idea_text")))
        if similarity < SAME_IDEA_THRESHOLD:
            continue
        # Idea ID는 날짜+일련번호라 문자열 비교로 최신 검토를 고를 수 있다
        if not best or record["idea_id"] > best["idea_id"]:
            best = record
    return best


def compare_with_previous(previous_idea_id: str, candidates: list) -> dict:
    """이전 검토의 수집 특허와 비교해 신규 발견/등급 상승을 계산한다."""
    previous = ideas.load_collected(previous_idea_id)
    previous_grades = {}
    for _, row in previous.iterrows():
        previous_grades[_patent_key(row)] = str(row.get("grade") or "")

    new_patents = []
    upgraded = []
    for candidate in candidates:
        key = _patent_key(candidate)
        if key not in previous_grades:
            new_patents.append(candidate)
            continue
        old_grade = previous_grades[key]
        new_grade = candidate.get("grade", "")
        if _GRADE_ORDER.get(new_grade, 0) > _GRADE_ORDER.get(old_grade, 0):
            upgraded.append({**candidate, "previous_grade": old_grade})

    return {
        "previous_idea_id": previous_idea_id,
        "new_patents": new_patents,
        "upgraded": upgraded,
    }


def comparison_summary(comparison: dict) -> str:
    if not comparison:
        return ""
    return (
        f"이전 검토({comparison['previous_idea_id']}) 대비 "
        f"신규 발견 {len(comparison['new_patents'])}건 · "
        f"등급 상승 {len(comparison['upgraded'])}건"
    )


def check_new_patents(idea: dict, max_results: int = 10) -> dict:
    """검토일 이후 새로 공개된 특허를 찾는다.

    검색 오류는 PatentSearchError 로 올라가므로 호출부에서 처리한다.
    """
    idea_id = idea.get("idea_id", "")
    keywords = [k.strip() for k in str(idea.get("keywords", "")).split(",") if k.strip()]
    if not keywords:
        return {"checked": 0, "new_patents": []}

    queries = build_search_queries(keywords)
    foreign_queries = build_foreign_queries(keywords)
    scope = idea.get("search_scope") or "국내특허"
    result = patent_search.run_search(scope, queries, foreign_queries)

    known = {
        _patent_key(row) for _, row in ideas.load_collected(idea_id).iterrows()
    }
    review_date = extract_compact_date(idea.get("created_at"))

    fresh = []
    for patent in result["patents"]:
        if _patent_key(patent) in known:
            continue
        published = extract_compact_date(patent.get("pub_date")) or extract_compact_date(
            patent.get("app_date")
        )
        if review_date and published and published >= review_date:
            fresh.append(patent)

    graded = (
        analyze(idea.get("idea_text", ""), keywords, fresh, max_results)
        if fresh
        else []
    )
    return {"checked": len(result["patents"]), "new_patents": graded}
