# -*- coding: utf-8 -*-
"""GPC IP Lens - KIPRISPlus API 클라이언트 (Adapter 구조).

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
from typing import List, Optional

import pandas as pd
import requests

from utils import cache_utils, config
from utils.text_utils import tokenize, split_keywords

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

    def __init__(self):
        self.base_url = config.get_kipris_base_url().rstrip("/")
        self.api_key = config.get_kipris_api_key()

    def search(self, query: str, max_results: int = 30) -> List[dict]:
        """특허 검색.

        TODO(실연동): KIPRISPlus '특허/실용신안 검색' API 호출.
        예시 (자유검색):
            GET {base_url}/patUtiModInfoSearchSevice/getWordSearch
            params: word=query, numOfRows=max_results, ServiceKey=api_key
        응답 XML 의 <item> 들을 PATENT_FIELDS 형태의 dict 로 매핑해서
        리스트로 반환해야 한다. (XML 파싱: xml.etree.ElementTree 사용 권장)
        """
        cache_key = f"kipris_search::{query}::{max_results}"
        cached = cache_utils.cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            url = f"{self.base_url}/patUtiModInfoSearchSevice/getWordSearch"
            resp = requests.get(
                url,
                params={"word": query, "numOfRows": max_results,
                        "ServiceKey": self.api_key},
                timeout=15,
            )
            resp.raise_for_status()
            # TODO(실연동): resp.text(XML) 을 파싱하여 results 리스트 구성
            # import xml.etree.ElementTree as ET
            # root = ET.fromstring(resp.text)
            # for item in root.iter("item"): ...
            results: List[dict] = []
            cache_utils.cache_set(cache_key, results)
            return results
        except requests.RequestException as exc:
            raise RuntimeError(f"KIPRIS API 호출 실패: {exc}") from exc

    def get_detail(self, application_no: str) -> Optional[dict]:
        """특허 상세정보 조회 (사용자가 클릭할 때만 호출, 결과는 캐싱).

        TODO(실연동): '서지상세정보' API 호출.
        예시:
            GET {base_url}/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch
            params: applicationNumber=application_no, ServiceKey=api_key
        """
        cache_key = f"kipris_detail::{application_no}"
        cached = cache_utils.cache_get(cache_key)
        if cached is not None:
            return cached
        # TODO(실연동): 실제 호출 및 파싱 구현 후 cache_utils.cache_set 호출
        return None

    def get_drawing_url(self, application_no: str) -> Optional[str]:
        """대표도면 URL 조회 (클릭 시 호출, 캐싱).

        TODO(실연동): '대표도면' API 호출.
        예시:
            GET {base_url}/patUtiModInfoSearchSevice/getRepresentativeDrawing
            params: applicationNumber=application_no, ServiceKey=api_key
        """
        cache_key = f"kipris_drawing::{application_no}"
        cached = cache_utils.cache_get(cache_key)
        if cached is not None:
            return cached or None
        # TODO(실연동): 실제 호출 구현
        return None


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
