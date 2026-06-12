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
