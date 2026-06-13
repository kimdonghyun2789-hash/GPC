# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - KIPRISPlus API 클라이언트 (Adapter 구조).

현재는 mock 모드(sample_patents.csv)로 동작한다.
실제 KIPRISPlus Open API 연동 시 RealKiprisAdapter 의 TODO 부분에
실제 endpoint 와 응답 파싱 코드를 추가하면 된다. 호출부(app.py)는
KiprisClient 인터페이스만 사용하므로 변경이 필요 없다.

KIPRISPlus 참고:
- 가입/키 발급: https://plus.kipris.or.kr
- 일반 검색 REST 예시(특허/실용신안 검색):
  GET {KIPRIS_BASE_URL}/patUtiModInfoSearchSevice/getWordSearch
      ?word={검색어}&ServiceKey={KIPRIS_API_KEY}
- 응답은 XML 이며 item 단위로 출원번호/발명의명칭/출원인/요약 등이 온다.
"""
import xml.etree.ElementTree as ET
from typing import List, Optional

import pandas as pd
import requests

from utils import cache_utils, config
from utils.text_utils import tokenize, split_keywords


def _xml_first(item, names):
    """item 하위에서 후보 태그명 중 처음 발견되는 텍스트를 반환.

    KIPRISPlus 응답은 서비스/버전에 따라 태그명이 조금씩 다르므로
    여러 후보를 순서대로 시도한다.
    """
    for n in names:
        el = item.find(n)
        if el is not None and (el.text or "").strip():
            return el.text.strip()
    return ""


def _fmt_date(raw: str) -> str:
    """KIPRIS 날짜(YYYYMMDD) → YYYY-MM-DD. 형식이 다르면 원문 유지."""
    d = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return str(raw or "")

# mock/실제 공통으로 사용하는 특허 레코드 필드
PATENT_FIELDS = [
    "application_no", "publication_no", "registration_no", "title",
    "applicant", "application_date", "publication_date", "registration_date",
    "status", "abstract", "representative_claim", "ipc", "cpc",
    "drawing_url", "kipris_url", "technology_group",
]


class MockKiprisAdapter:
    """sample_patents.csv 기반 mock 어댑터."""

    def __init__(self):
        self._df: Optional[pd.DataFrame] = None

    def _load(self) -> pd.DataFrame:
        if self._df is None:
            self._df = pd.read_csv(config.SAMPLE_CSV, dtype=str).fillna("")
        return self._df

    def search(self, query: str, max_results: int = 30) -> List[dict]:
        """검색식의 토큰과 특허 텍스트 토큰의 겹침 정도로 정렬해 반환.

        KIPRIS 검색식 구분자(* AND OR + 공백)를 모두 토큰으로 분해한다.
        """
        df = self._load()
        q_tokens = set(tokenize(query.replace("*", " ").replace("+", " ")))
        if not q_tokens:
            return df.head(max_results).to_dict("records")

        scored = []
        for _, row in df.iterrows():
            text = " ".join([row["title"], row["abstract"],
                             row["representative_claim"],
                             row["technology_group"]])
            doc_tokens = set(tokenize(text))
            # 부분 문자열 매칭 포함 (예: '배수' vs '배수구조')
            hits = sum(
                1 for q in q_tokens
                if q in doc_tokens or any(q in d or d in q for d in doc_tokens)
            )
            if hits > 0:
                scored.append((hits, row.to_dict()))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [r for _, r in scored[:max_results]]
        # 매칭이 전혀 없으면 빈 결과 대신 전체 상위를 반환해 화면이 죽지 않게 한다
        if not results:
            results = df.head(min(10, max_results)).to_dict("records")
        return results

    def get_detail(self, application_no: str) -> Optional[dict]:
        df = self._load()
        rows = df[df["application_no"] == application_no]
        return rows.iloc[0].to_dict() if len(rows) else None

    def get_drawing_url(self, application_no: str) -> Optional[str]:
        detail = self.get_detail(application_no)
        return (detail or {}).get("drawing_url") or None


class RealKiprisAdapter:
    """실제 KIPRISPlus Open API 어댑터.

    TODO(실연동): 아래 각 메서드에 실제 endpoint 호출/XML 파싱을 구현한다.
    Settings 화면(또는 .env)에서 KIPRIS_API_KEY / KIPRIS_BASE_URL 을
    입력하고 USE_MOCK_DATA=false 로 바꾸면 이 어댑터가 사용된다.
    """

    # KIPRISPlus 특허·실용신안 서비스 오퍼레이션 (필요 시 BASE_URL 뒤 경로만 수정)
    SEARCH_OP = "/patUtiModInfoSearchSevice/getWordSearch"
    DETAIL_OP = "/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch"
    DRAWING_OP = "/patUtiModInfoSearchSevice/getRepresentativeDrawingInfo"

    def __init__(self):
        self.base_url = config.get_kipris_base_url().rstrip("/")
        self.api_key = config.get_kipris_api_key()

    def _call(self, op: str, params: dict) -> ET.Element:
        """오퍼레이션 호출 후 XML 루트 반환."""
        url = f"{self.base_url}{op}"
        p = dict(params)
        p["ServiceKey"] = self.api_key
        resp = requests.get(url, params=p, timeout=20)
        resp.raise_for_status()
        return ET.fromstring(resp.text)

    @staticmethod
    def _kipris_url(app_no: str) -> str:
        digits = "".join(ch for ch in str(app_no) if ch.isdigit())
        return (f"http://kpat.kipris.or.kr/kpat/biblioa.do?applno={digits}"
                if digits else "")

    def _parse_item(self, item: ET.Element) -> dict:
        """KIPRIS <item> → PATENT_FIELDS dict (태그명 변형에 관대하게)."""
        app_no = _xml_first(item, ["applicationNumber", "ApplicationNumber",
                                   "appReferenceNumber"])
        return {
            "application_no": app_no,
            "publication_no": _xml_first(item, ["openNumber", "publicationNumber",
                                                "publicationNo"]),
            "registration_no": _xml_first(item, ["registerNumber",
                                                 "registrationNumber"]),
            "title": _xml_first(item, ["inventionTitle", "InventionName",
                                       "title", "astrtContTitle"]),
            "applicant": _xml_first(item, ["applicantName", "ApplicantName",
                                           "applicant"]),
            "application_date": _fmt_date(_xml_first(
                item, ["applicationDate", "ApplicationDate"])),
            "publication_date": _fmt_date(_xml_first(
                item, ["openDate", "publicationDate", "PublicationDate"])),
            "registration_date": _fmt_date(_xml_first(
                item, ["registerDate", "registrationDate"])),
            "status": _xml_first(item, ["registerStatus", "applicationStatus",
                                        "registerStatusName"]),
            "abstract": _xml_first(item, ["astrtCont", "abstractContent",
                                          "abstract"]),
            "representative_claim": _xml_first(item, ["claimScope", "claim",
                                                      "claimContent"]),
            "ipc": _xml_first(item, ["ipcNumber", "ipcCode", "ipc"]),
            "cpc": _xml_first(item, ["cpcNumber", "cpcCode", "cpc"]),
            "drawing_url": _xml_first(item, ["bigDrawing", "drawing",
                                             "imagePath", "drawingPath"]),
            "kipris_url": self._kipris_url(app_no),
            "technology_group": "",
        }

    def search(self, query: str, max_results: int = 30) -> List[dict]:
        """KIPRISPlus 자유검색. 응답 XML 의 <item> 을 PATENT_FIELDS 로 매핑.

        주: 실제 응답에서 태그명이 다르면 _parse_item 의 후보 목록만 보완하면
        된다. (응답 샘플 XML 을 한 번 확인하면 정확히 고정 가능)
        """
        cache_key = f"kipris_search::{query}::{max_results}"
        cached = cache_utils.cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            root = self._call(self.SEARCH_OP, {
                "word": query, "numOfRows": max_results, "pageNo": 1,
                "patent": "true", "utility": "true"})
        except (requests.RequestException, ET.ParseError) as exc:
            raise RuntimeError(f"KIPRIS API 호출 실패: {exc}") from exc

        results = []
        for item in root.iter("item"):
            rec = self._parse_item(item)
            if rec["application_no"] or rec["title"]:
                results.append(rec)
        cache_utils.cache_set(cache_key, results)
        return results

    def get_detail(self, application_no: str) -> Optional[dict]:
        """서지상세정보 조회 (클릭 시 호출, 결과 캐싱)."""
        cache_key = f"kipris_detail::{application_no}"
        cached = cache_utils.cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            root = self._call(self.DETAIL_OP,
                              {"applicationNumber": application_no})
        except (requests.RequestException, ET.ParseError):
            return None
        item = next(root.iter("item"), None)
        detail = self._parse_item(item) if item is not None else None
        if detail:
            cache_utils.cache_set(cache_key, detail)
        return detail

    def get_drawing_url(self, application_no: str) -> Optional[str]:
        """대표도면 URL 조회 (클릭 시 호출, 캐싱)."""
        cache_key = f"kipris_drawing::{application_no}"
        cached = cache_utils.cache_get(cache_key)
        if cached is not None:
            return cached or None
        try:
            root = self._call(self.DRAWING_OP,
                              {"applicationNumber": application_no})
        except (requests.RequestException, ET.ParseError):
            return None
        url = _xml_first(root, ["path", "drawing", "bigDrawing", "imagePath"])
        if not url:
            item = next(root.iter("item"), None)
            if item is not None:
                url = _xml_first(item, ["path", "drawing", "bigDrawing",
                                        "imagePath"])
        cache_utils.cache_set(cache_key, url or "")
        return url or None


class KiprisClient:
    """호출부가 사용하는 단일 진입점. mock/real 어댑터를 자동 선택한다."""

    def __init__(self):
        if config.use_mock_data():
            self.adapter = MockKiprisAdapter()
            self.mode = "mock"
        else:
            self.adapter = RealKiprisAdapter()
            self.mode = "real"

    def search_multi(self, queries: List[str], per_query: int = 25,
                     exclude_keywords: str = "") -> List[dict]:
        """검색식 상위 3~5개를 실행하고 출원번호 기준으로 중복 제거."""
        seen = set()
        merged: List[dict] = []
        excludes = [e.lower() for e in split_keywords(exclude_keywords)]
        for query in queries[:5]:
            try:
                items = self.adapter.search(query, max_results=per_query)
            except RuntimeError:
                continue
            for item in items:
                key = (item.get("application_no")
                       or item.get("publication_no")
                       or item.get("registration_no")
                       or item.get("title"))
                if not key or key in seen:
                    continue
                text = f"{item.get('title','')} {item.get('abstract','')}".lower()
                if any(ex and ex in text for ex in excludes):
                    continue
                seen.add(key)
                item["search_query"] = query
                merged.append(item)
        return merged

    def get_detail(self, application_no: str) -> Optional[dict]:
        return self.adapter.get_detail(application_no)

    def get_drawing_url(self, application_no: str) -> Optional[str]:
        return self.adapter.get_drawing_url(application_no)
