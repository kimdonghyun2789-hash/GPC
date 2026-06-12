"""공통 유틸리티: 토큰화, 유사도 기초 함수, 날짜 처리."""
import re
from datetime import datetime

# 기술 문장에서 의미가 약한 한국어 단어
STOPWORDS = {
    "그리고", "또는", "또한", "있는", "없는", "하는", "되는", "위한", "통해",
    "대한", "의한", "있다", "한다", "된다", "이를", "경우", "때문", "관련",
    "이상", "이하", "다양", "가능", "제공", "포함", "사용", "이용", "기존",
    "해당", "각각", "하나", "구비", "형성", "방법", "장치", "시스템", "발명",
}

# 단어 끝의 조사/어미를 제거하기 위한 목록(긴 것 우선)
_JOSA = sorted(
    [
        "으로부터", "에서는", "에게서", "으로서", "으로써", "이라는", "라는",
        "에서", "에게", "으로", "까지", "부터", "처럼", "보다", "마다",
        "와의", "과의", "은", "는", "이", "가", "을", "를", "과", "와",
        "로", "에", "의", "도", "만",
        "하여", "되어", "하는", "되는", "하고", "되고", "하기", "되기",
        "시켜", "시키는", "된", "한",
    ],
    key=len,
    reverse=True,
)

_TOKEN_RE = re.compile(r"[가-힣]+|[A-Za-z]+|[0-9]+")
_HANGUL_RE = re.compile(r"^[가-힣]")
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _strip_josa(token: str) -> str:
    for josa in _JOSA:
        if token.endswith(josa) and len(token) - len(josa) >= 2:
            return token[: -len(josa)]
    return token


def tokenize(text) -> list:
    """한국어/영문 혼합 기술 문장을 키워드 토큰 목록으로 변환한다."""
    tokens = []
    for raw in _TOKEN_RE.findall(str(text or "")):
        token = _strip_josa(raw) if _HANGUL_RE.match(raw) else raw.lower()
        if len(token) >= 2 and token not in STOPWORDS:
            tokens.append(token)
    return tokens


def token_set(text) -> set:
    return set(tokenize(text))


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap_ratio(base: set, other: set) -> float:
    """base 집합 기준으로 other 와 겹치는 비율."""
    if not base:
        return 0.0
    return len(base & other) / len(base)


def extract_compact_date(value) -> str:
    """날짜 표기에서 YYYYMMDD 8자리를 추출한다. 실패 시 빈 문자열."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:8] if len(digits) >= 8 else ""


def extract_year(*dates) -> str:
    for value in dates:
        match = _YEAR_RE.search(str(value or ""))
        if match:
            return match.group()
    return ""


def today_compact() -> str:
    return datetime.now().strftime("%Y%m%d")


def now_display() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
