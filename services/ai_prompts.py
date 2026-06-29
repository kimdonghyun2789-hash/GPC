"""
services/ai_prompts.py
prompts/ 폴더의 마크다운 프롬프트 템플릿을 로드하고 변수를 채운다.
- 파일이 없으면 코드에 내장된 기본 프롬프트로 폴백한다.
- {변수} 형태의 플레이스홀더를 안전하게 치환한다(없는 변수는 그대로 둔다).
"""

from __future__ import annotations

import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROMPT_DIR = os.path.join(_BASE_DIR, "prompts")

# 파일이 없을 때 사용할 내장 기본 프롬프트
_FALLBACK = {
    "recommendation_comment": (
        "너는 회사 점심 추천 도우미다. 아래 추천 결과를 보고 짧고 실용적인 코멘트를 "
        "각 순위별 2~3문장으로 작성해라. 과장하지 말 것.\n입력 데이터:\n{recommendation_data}\n"
        "출력 형식:\n1순위 코멘트:\n2순위 코멘트:\n3순위 코멘트:"
    ),
    "memo_analysis": (
        "너는 점심 식당 방문 메모를 분석하는 도우미다. 아래 메모를 분석해 JSON으로만 답해라.\n"
        "식당명: {restaurant_name}\n메뉴분류: {category}\n방문 메모: {memo}\n만족도: {satisfaction}\n"
        '출력 JSON: {"summary": "한 줄 요약", "sentiment": "좋음/보통/나쁨", '
        '"tags": ["태그1","태그2"], "recommendation_impact": "가점/유지/감점"}'
    ),
    "budget_advice": (
        "너는 회사 점심 예산 관리 도우미다. 아래 데이터를 보고 현재 상태 요약, 초과 가능성, "
        "추천 전략을 짧게 제안해라.\n월 예산: {monthly_budget}\n현재 사용금액: {spent_amount}\n"
        "남은 예산: {remaining_budget}\n예산 사용률: {usage_rate}\n평균 점심 비용: {avg_lunch_price}\n"
        "남은 근무일 수: {remaining_workdays}"
    ),
    "monthly_report": (
        "너는 회사 점심 리포트 작성 도우미다. 아래 월간 데이터를 바탕으로 자연스러운 한국어 "
        "리포트를 작성해라.\n{report_data}"
    ),
}


def load_template(name: str) -> str:
    """prompts/{name}.md 를 읽고, 없으면 내장 기본 프롬프트를 반환한다."""
    path = os.path.join(_PROMPT_DIR, f"{name}.md")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass
    return _FALLBACK.get(name, "")


def render(name: str, **kwargs) -> str:
    """템플릿을 로드한 뒤 {변수}를 치환한다. 없는 변수는 그대로 둔다."""
    template = load_template(name)
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    return template
