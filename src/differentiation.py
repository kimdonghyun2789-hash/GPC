"""차별화 포인트 초안 생성 (목적/구성/적용 단계/효과)."""

DIFF_FIELDS = [
    ("diff_purpose", "목적 차이"),
    ("diff_structure", "구성 차이"),
    ("diff_stage", "적용 단계 차이"),
    ("diff_effect", "효과 차이"),
]


def build_draft(idea_text: str, keywords: list, claim_mapping_df) -> dict:
    """청구항 키워드 매칭 결과를 바탕으로 4개 관점의 초안을 만든다."""
    unique_keywords = []
    overlapped_keywords = []
    if claim_mapping_df is not None and not claim_mapping_df.empty:
        for _, row in claim_mapping_df.iterrows():
            keyword = row["아이디어 구성요소"]
            if row["유사특허 포함 여부"] == "없음":
                unique_keywords.append(keyword)
            elif row["유사특허 포함 여부"] in ("있음", "일부 있음"):
                overlapped_keywords.append(keyword)

    unique_text = ", ".join(unique_keywords[:4]) if unique_keywords else ""
    overlap_text = ", ".join(overlapped_keywords[:4]) if overlapped_keywords else ""

    purpose = (
        "본 아이디어는 "
        + (f"'{unique_text}' 요소를 중심으로 " if unique_text else "")
        + "기존 유사특허와 해결하려는 과제가 어떻게 다른지 정리합니다. "
        "(예: 기존 특허는 사후 처리 중심, 본 아이디어는 사전 예방 중심)"
    )
    structure = (
        (
            f"유사특허에서 확인되지 않은 구성요소: {unique_text}. "
            if unique_text
            else "유사특허와 구분되는 고유 구성요소를 정리합니다. "
        )
        + (
            f"중복 가능성이 있는 구성요소({overlap_text})는 결합 방식이나 "
            "배치의 차이를 구체적으로 기재합니다."
            if overlap_text
            else "구성요소의 결합 방식 차이를 구체적으로 기재합니다."
        )
    )
    stage = (
        "본 아이디어가 적용되는 단계(제조/시공/운영/유지보수 등)가 "
        "유사특허와 어떻게 다른지 정리합니다. "
        "(예: 공장 제작 단계 선매립 vs 현장 시공 단계 후설치)"
    )
    effect = (
        "구성 차이로부터 발생하는 효과 차이를 정리합니다. "
        "(예: 공정 단축, 품질 안정화, 유지보수 비용 절감 등 정량적 효과 포함)"
    )

    return {
        "diff_purpose": purpose,
        "diff_structure": structure,
        "diff_stage": stage,
        "diff_effect": effect,
    }
