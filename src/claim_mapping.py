"""청구항 키워드 매칭 (기술 검토 보조 기능).

아이디어 구성요소(핵심 키워드)가 유사특허의 청구항/요약/제목에
포함되는지 확인해 매칭표를 만든다.
"""
import pandas as pd

from src.utils import token_set

# 매칭표 확인 대상 유사특허 수
TOP_PATENTS_TO_CHECK = 5


def _patent_label(patent: dict) -> str:
    return (
        patent.get("pub_number")
        or patent.get("app_number")
        or str(patent.get("title", ""))[:20]
    )


def build_claim_mapping(keywords: list, candidates: list) -> pd.DataFrame:
    """컬럼: 아이디어 구성요소 / 유사특허 포함 여부 / 판단 / 근거·메모"""
    targets = candidates[:TOP_PATENTS_TO_CHECK]
    rows = []
    for keyword in keywords:
        in_claims, in_text, no_text = [], [], []
        for patent in targets:
            claims_tokens = token_set(patent.get("claims"))
            text_tokens = token_set(patent.get("title")) | token_set(
                patent.get("abstract")
            )
            label = _patent_label(patent)
            if not claims_tokens and not text_tokens:
                no_text.append(label)
            elif keyword in claims_tokens:
                in_claims.append(label)
            elif keyword in text_tokens:
                in_text.append(label)

        if in_claims:
            included, judgement = "있음", "유사"
            note = f"청구항 포함: {', '.join(in_claims[:3])}"
        elif in_text:
            included, judgement = "일부 있음", "일부 유사"
            note = f"제목/요약 포함: {', '.join(in_text[:3])}"
        elif targets and not no_text:
            included, judgement = "없음", "차별 가능"
            note = f"상위 {len(targets)}건의 유사특허에서 확인되지 않음"
        else:
            included, judgement = "확인 필요", "확인 필요"
            note = "원문 확인이 필요합니다"

        rows.append(
            {
                "아이디어 구성요소": keyword,
                "유사특허 포함 여부": included,
                "판단": judgement,
                "근거/메모": note,
            }
        )
    return pd.DataFrame(rows)
