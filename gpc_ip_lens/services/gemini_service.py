# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - Gemini API 서비스 래퍼.

모든 함수는 실패 시 None 을 반환한다. 호출부는 None 이면 fallback 로직을
사용해야 한다. API Key 는 utils.config 를 통해서만 읽는다 (하드코딩 금지).
"""
import json
import re
from typing import List, Optional

from utils import config

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    genai = None
    _GENAI_AVAILABLE = False

TEXT_MODEL = "gemini-1.5-flash"
EMBED_MODEL = "models/text-embedding-004"


def is_available() -> bool:
    """Gemini SDK 와 API Key 가 모두 준비되었는지 확인."""
    return _GENAI_AVAILABLE and bool(config.get_gemini_api_key())


def _get_model():
    if not is_available():
        return None
    try:
        genai.configure(api_key=config.get_gemini_api_key())
        return genai.GenerativeModel(TEXT_MODEL)
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
    model = _get_model()
    if model is None:
        return None
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception:
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
    prompt = f"""당신은 건설/프리캐스트 콘크리트(PC) 분야 특허 검색 전문가입니다.
아래 아이디어를 분석하여 KIPRIS 특허 검색에 사용할 검색어를 확장하세요.

아이디어명: {idea_title}
아이디어 설명: {idea_description}
핵심 키워드: {keywords}
제외 키워드: {exclude_keywords}

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트를 추가하지 마세요.
{{
  "korean_keywords": ["국문 키워드 5~10개"],
  "english_keywords": ["영문 키워드 5~10개"],
  "synonyms": ["동의어"],
  "exclude_keywords": ["제외어"],
  "search_queries": ["KIPRIS 검색식 후보 3~5개 (예: 프리캐스트*기둥*접합)"],
  "technology_groups": ["기술군 후보 (접합부/전단키/생산방법/몰드/배수/방수/품질관리/유지관리/센서/시공장비/기타 중에서)"],
  "idea_dna": {{
    "target": "대상 기술/부재",
    "problem": "해결하려는 문제",
    "solution": "해결수단",
    "components": ["구성요소"],
    "stage": "적용시점 (생산/시공/유지관리 등)",
    "method": "제조/시공방법",
    "effect": "효과",
    "technology_group": "대표 기술군"
  }}
}}"""
    return generate_json(prompt)


# ----------------------------------------------------------- 특허 DNA 추출
def extract_patent_dna(title: str, abstract: str, claim: str) -> Optional[dict]:
    prompt = f"""당신은 건설/PC 분야 특허 분석 전문가입니다.
아래 특허에서 특허 DNA 를 추출하세요.

특허명: {title}
요약: {abstract}
대표청구항: {claim}

반드시 아래 JSON 형식으로만 응답하세요.
{{
  "target": "대상 기술/부재",
  "problem": "해결하려는 문제",
  "solution": "해결수단",
  "components": ["구성요소"],
  "stage": "적용시점",
  "method": "제조/시공방법",
  "effect": "효과"
}}"""
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
    prompt = f"""당신은 건설/PC 분야 특허 1차 검토 보조 도구입니다.
법률 판단을 단정하지 말고 '검토 가능성', '확인 필요', '변리사 검토 필요'
같은 참고 의견 수준으로만 표현하세요.

{review_input}

반드시 아래 JSON 형식으로만 응답하세요.
{{
  "most_risky_patents": ["가장 유사한 특허명과 이유"],
  "common_points": ["내 아이디어와 공통 구성"],
  "different_points": ["차이 구성"],
  "key_differentiators": ["핵심 차별 포인트"],
  "claim_check_points": ["청구항 확인 필요 문구"],
  "design_around_points": ["회피설계 검토 포인트"],
  "review_comment": "출원 검토 참고 의견 (단정 금지, 최종 법률 판단 아님 명시)"
}}"""
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
    model = _get_model()
    if model is None:
        return None
    try:
        response = model.generate_content([
            "이 건설/PC 관련 도면 이미지에서 식별 가능한 구성요소를 "
            "한국어 불릿 목록으로 추출하세요.",
            {"mime_type": mime_type, "data": image_bytes},
        ])
        return response.text
    except Exception:
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
