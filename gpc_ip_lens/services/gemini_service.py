# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - Gemini API 서비스 래퍼.

모든 함수는 실패 시 None 을 반환한다. 호출부는 None 이면 fallback 로직을
사용해야 한다. API Key 는 utils.config 를 통해서만 읽는다 (하드코딩 금지).
"""
import json
import re
from typing import List, Optional

from utils import config, prompts

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    genai = None
    _GENAI_AVAILABLE = False

# 무료(AI Studio) 키에서 가용한 최신 모델 우선. 키/리전별 차이를 위해
# 앞에서부터 시도하고, 성공한 모델을 기억해 재사용한다.
TEXT_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
EMBED_MODEL = "models/text-embedding-004"
_working_model = None


def is_available() -> bool:
    """Gemini SDK 와 API Key 가 모두 준비되었는지 확인."""
    return _GENAI_AVAILABLE and bool(config.get_gemini_api_key())


def _candidate_models():
    return [_working_model] if _working_model else TEXT_MODELS


def _get_model():
    """현재 동작 모델(또는 1순위) GenerativeModel 반환. 실패 시 None."""
    if not is_available():
        return None
    try:
        genai.configure(api_key=config.get_gemini_api_key())
        return genai.GenerativeModel(_candidate_models()[0])
    except Exception:
        return None


def _extract_json(text: str) -> Optional[dict]:
    """Gemini 응답에서 JSON 블록을 파싱한다. 실패 시 None."""
    if not text:
        return None
    # ```json ... ``` 코드펜스 제거
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(),
                     flags=re.MULTILINE)
    for candidate in (cleaned, text):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            pass
    # 본문 중 가장 바깥 { } 만 추출 시도
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _generate(prompt: str) -> Optional[str]:
    """후보 모델을 순서대로 시도하고 성공 모델을 기억한다. 실패 시 None."""
    global _working_model
    if not is_available():
        return None
    try:
        genai.configure(api_key=config.get_gemini_api_key())
    except Exception:
        return None
    for mid in _candidate_models():
        try:
            response = genai.GenerativeModel(mid).generate_content(prompt)
            _working_model = mid
            return response.text
        except Exception:
            if _working_model == mid:
                _working_model = None  # 다음엔 전체 후보 재시도
            continue
    return None


def generate_json(prompt: str) -> Optional[dict]:
    """프롬프트를 보내고 JSON 응답을 파싱. 실패 시 None (fallback 필요)."""
    text = _generate(prompt)
    if text is None:
        return None
    return _extract_json(text)


def generate_text(prompt: str) -> Optional[str]:
    return _generate(prompt)


# ------------------------------------------------------------- 검색어 확장
def expand_keywords(idea_title: str, idea_description: str,
                    keywords: str, exclude_keywords: str) -> Optional[dict]:
    """아이디어 설명을 받아 검색어 확장 JSON 을 반환한다."""
    prompt = prompts.render(
        "keyword_expand", idea_title=idea_title,
        idea_description=idea_description, keywords=keywords,
        exclude_keywords=exclude_keywords)
    if prompt is None:
        prompt = (
            "당신은 건설/PC 분야 특허 검색 전문가입니다. 아래 아이디어로 "
            "KIPRIS 검색어를 확장해 korean_keywords, english_keywords, "
            "synonyms, exclude_keywords, search_queries, technology_groups, "
            "idea_dna 키를 가진 JSON 으로만 응답하세요.\n"
            f"아이디어명: {idea_title}\n설명: {idea_description}\n"
            f"키워드: {keywords}\n제외: {exclude_keywords}")
    return generate_json(prompt)


# ----------------------------------------------------------- 특허 DNA 추출
def extract_patent_dna(title: str, abstract: str, claim: str) -> Optional[dict]:
    prompt = prompts.render("patent_dna", title=title, abstract=abstract,
                            claim=claim)
    if prompt is None:
        prompt = (
            "당신은 건설/PC 분야 특허 분석 전문가입니다. 아래 특허에서 "
            "target, problem, solution, components, stage, stages, method, "
            "effect 키를 가진 특허 DNA JSON 으로만 응답하세요.\n"
            f"특허명: {title}\n요약: {abstract}\n대표청구항: {claim}")
    return generate_json(prompt)


# --------------------------------------------------------- 기술발전도 문장화
def narrate_timeline(timeline_summary: str) -> Optional[str]:
    prompt = f"""당신은 건설/PC 분야 기술 동향 분석가입니다.
아래 연도별 특허 출원 데이터를 바탕으로 기술발전 흐름을
'2015~2018: 접합부 및 기본 구조 중심' 형식의 구간별 불릿 4~6개로
한국어로 요약하세요. 데이터에 없는 내용은 추측하지 마세요.

{timeline_summary}"""
    return generate_text(prompt)


# ----------------------------------------------------------- AI 특허 검토
def review_patents(review_input: str) -> Optional[dict]:
    prompt = prompts.render("ai_review", review_input=review_input)
    if prompt is None:
        prompt = (
            "당신은 건설/PC 분야 특허 1차 검토 보조 도구입니다. 법률 판단을 "
            "단정하지 말고 참고 의견 수준으로만 표현하세요. most_risky_patents, "
            "common_points, different_points, key_differentiators, "
            "claim_check_points, design_around_points, review_comment 키를 "
            f"가진 JSON 으로만 응답하세요.\n\n{review_input}")
    return generate_json(prompt)


# ------------------------------------------------------- 청구항 초안 (보완안)
def draft_claims(idea_title: str, idea_description: str,
                 differentiators: str, prior_art: str) -> Optional[dict]:
    prompt = prompts.render(
        "claim_draft", idea_title=idea_title,
        idea_description=idea_description, differentiators=differentiators,
        prior_art=prior_art)
    if prompt is None:
        prompt = (
            "당신은 건설/PC 분야 특허 출원 보조 도구입니다. 차별화를 반영한 "
            "independent_claim, dependent_claims, method_claim, design_around, "
            "notes 키를 가진 청구항 초안 JSON 으로만 응답하세요. 최종 법률 "
            f"문서가 아닌 참고 초안입니다.\n아이디어명: {idea_title}\n"
            f"설명: {idea_description}\n차별 포인트: {differentiators}\n"
            f"유사특허 청구항 요지: {prior_art}")
    return generate_json(prompt)


# ------------------------------------------------------------- 도면 캡션
def caption_drawing(title: str, abstract: str) -> Optional[str]:
    prompt = f"""아래 건설/PC 특허의 대표도면에 들어갈 12자 내외의 짧은
한국어 캡션 1개만 출력하세요. (예: '중공기둥 하부 배수구조')

특허명: {title}
요약: {abstract}"""
    text = generate_text(prompt)
    if text:
        return text.strip().splitlines()[0][:40]
    return None


def analyze_uploaded_image(image_bytes: bytes, mime_type: str) -> Optional[str]:
    """Gemini Vision 으로 업로드 도면에서 구성요소를 추출한다."""
    global _working_model
    if not is_available():
        return None
    try:
        genai.configure(api_key=config.get_gemini_api_key())
    except Exception:
        return None
    parts = [
        "이 건설/PC 관련 도면 이미지에서 식별 가능한 구성요소를 "
        "한국어 불릿 목록으로 추출하세요.",
        {"mime_type": mime_type, "data": image_bytes},
    ]
    for mid in _candidate_models():
        try:
            response = genai.GenerativeModel(mid).generate_content(parts)
            _working_model = mid
            return response.text
        except Exception:
            continue
    return None


# ----------------------------------------------------------------- 임베딩
def embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """Gemini 임베딩 (텍스트별 파일 캐시). 실패 시 None → TF-IDF fallback.

    동일 텍스트는 캐시에서 재사용하여 재검색 시 API 호출/비용을 줄인다.
    """
    if not is_available():
        return None
    import hashlib
    from utils import cache_utils
    try:
        genai.configure(api_key=config.get_gemini_api_key())
        vectors = []
        for text in texts:
            snippet = (text or "")[:8000]
            key = ("emb::" + EMBED_MODEL + "::"
                   + hashlib.md5(snippet.encode("utf-8")).hexdigest())
            cached = cache_utils.cache_get(key)
            if isinstance(cached, list) and cached:
                vectors.append(cached)
                continue
            result = genai.embed_content(
                model=EMBED_MODEL, content=snippet,
                task_type="semantic_similarity")
            vec = result["embedding"]
            cache_utils.cache_set(key, vec)
            vectors.append(vec)
        return vectors
    except Exception:
        return None
