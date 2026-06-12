"""KIPRISPlus 기반 특허 검색 소스.

국내/해외 특허 검색을 호출하고 응답을 공통 dict 형태로 정규화한다.
응답 형식은 환경변수 KIPRIS_API_FORMAT(xml)을 따른다.
"""
import xml.etree.ElementTree as ET

import requests

from src import config


class PatentSearchError(Exception):
    """사용자에게는 짧은 안내만 보여주고, detail 에 원인을 담는다."""

    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.detail = detail


# 응답 XML 태그가 서비스마다 조금씩 달라 후보 태그를 함께 둔다.
_FIELD_TAGS = {
    "title": ["inventionTitle", "inventionName", "title", "inventionTitleEng"],
    "applicant": ["applicantName", "applicant"],
    "app_number": ["applicationNumber", "appNumber"],
    "app_date": ["applicationDate", "appDate"],
    "pub_number": ["openNumber", "publicationNumber", "publicNumber", "laidOpenNumber"],
    "pub_date": ["openDate", "publicationDate", "publicDate", "laidOpenDate"],
    "reg_number": ["registerNumber", "registrationNumber"],
    "reg_date": ["registerDate", "registrationDate"],
    "status": ["registerStatus", "applicationStatus", "legalStatus"],
    "ipc": ["ipcNumber", "ipcCode", "internationalpatentclassificationNumber", "mainIpc"],
    "abstract": ["astrtCont", "abstractContents", "abstract", "summary"],
    "country": ["countryCode", "country", "countryName"],
    "claims": ["claim", "claims", "claimScope"],
    "link": ["docsUrl", "originUrl", "linkUrl"],
}


def _find_text(item: ET.Element, tags: list) -> str:
    for tag in tags:
        element = item.find(f".//{tag}")
        if element is not None and (element.text or "").strip():
            return element.text.strip()
    return ""


def _request(url: str, params: dict) -> str:
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise PatentSearchError(
            config.SEARCH_UNAVAILABLE_MESSAGE,
            detail=f"요청 실패: {exc}",
        ) from exc


def _check_api_error(root: ET.Element, raw: str) -> None:
    success = root.findtext(".//successYN")
    if success and success.strip().upper() == "N":
        message = root.findtext(".//resultMsg") or "원인 미상"
        raise PatentSearchError(
            config.SEARCH_UNAVAILABLE_MESSAGE,
            detail=f"응답 오류: {message.strip()}",
        )
    result_code = root.findtext(".//resultCode")
    if result_code and result_code.strip() not in ("", "0", "00"):
        message = root.findtext(".//resultMsg") or raw[:300]
        raise PatentSearchError(
            config.SEARCH_UNAVAILABLE_MESSAGE,
            detail=f"응답 코드 {result_code.strip()}: {message.strip()}",
        )


def _parse_items(raw: str, source: str) -> list:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise PatentSearchError(
            config.SEARCH_UNAVAILABLE_MESSAGE,
            detail=f"응답 해석 실패: {exc} / 응답 일부: {raw[:300]}",
        ) from exc

    _check_api_error(root, raw)

    patents = []
    for item in root.iter("item"):
        record = {field: _find_text(item, tags) for field, tags in _FIELD_TAGS.items()}
        if not record["title"]:
            continue
        record["source"] = source
        if source == "국내":
            record["country"] = "KR"
            if not record["link"] and record["app_number"]:
                record["link"] = (
                    "http://kpat.kipris.or.kr/kpat/biblioa.do"
                    f"?method=biblioFrame&applno={record['app_number']}"
                )
        else:
            record["country"] = record["country"] or "해외"
        patents.append(record)
    return patents


def _search(url: str, query: str, rows: int, source: str) -> list:
    params = {
        "word": query,
        "ServiceKey": config.KIPRIS_API_KEY,
        "numOfRows": rows,
        "pageNo": 1,
    }
    raw = _request(url, params)
    return _parse_items(raw, source)


def search_kr(query: str, rows: int = 100) -> list:
    if not config.kr_search_configured():
        raise PatentSearchError(
            config.SEARCH_UNAVAILABLE_MESSAGE,
            detail="국내 검색 설정값(KIPRIS_API_KEY, KIPRIS_KR_API_URL)이 비어 있습니다.",
        )
    return _search(config.KIPRIS_KR_API_URL, query, rows, "국내")


def search_foreign(query: str, rows: int = 100) -> list:
    if not config.foreign_search_configured():
        raise PatentSearchError(
            config.SEARCH_UNAVAILABLE_MESSAGE,
            detail="해외 검색 설정값(KIPRIS_API_KEY, KIPRIS_FOREIGN_API_URL)이 비어 있습니다.",
        )
    return _search(config.KIPRIS_FOREIGN_API_URL, query, rows, "해외")


# ---------------------------------------------------------------------------
# 청구항 상세 조회 (보조 기능 — 실패해도 검토 흐름은 계속 진행한다)
# ---------------------------------------------------------------------------
_CLAIM_TEXT_TAGS = ["claimTextKor", "claimText", "claim", "claimScope"]
_claims_cache = {}


def claims_lookup_configured() -> bool:
    return bool(config.KIPRIS_API_KEY and config.KIPRIS_KR_DETAIL_API_URL)


def fetch_claims(app_number: str) -> str:
    """출원번호로 청구항 원문을 조회한다. 실패 시 빈 문자열을 반환한다."""
    app_number = str(app_number or "").strip().replace("-", "")
    if not app_number or not claims_lookup_configured():
        return ""
    if app_number in _claims_cache:
        return _claims_cache[app_number]

    claims = ""
    try:
        raw = _request(
            config.KIPRIS_KR_DETAIL_API_URL,
            {"applicationNumber": app_number, "ServiceKey": config.KIPRIS_API_KEY},
        )
        root = ET.fromstring(raw)
        texts = []
        for tag in _CLAIM_TEXT_TAGS:
            for element in root.iter(tag):
                text = (element.text or "").strip()
                if text:
                    texts.append(text)
            if texts:
                break
        claims = "\n".join(
            f"{i}. {t}" if not t[:3].strip().rstrip(".").isdigit() else t
            for i, t in enumerate(texts, start=1)
        )
    except (PatentSearchError, ET.ParseError):
        claims = ""

    _claims_cache[app_number] = claims
    return claims


def enrich_claims(patents: list, limit: int = 5) -> None:
    """국내특허 상위 limit건에 청구항 원문을 채운다 (가능한 경우에만)."""
    if not claims_lookup_configured():
        return
    count = 0
    for patent in patents:
        if count >= limit:
            break
        if patent.get("source") != "국내" or patent.get("claims"):
            continue
        claims = fetch_claims(patent.get("app_number"))
        if claims:
            patent["claims"] = claims
        count += 1
