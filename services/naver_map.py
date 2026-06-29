"""
services/naver_map.py
네이버 지도(NAVER Cloud Platform Maps) 연동 — 선택 기능.
- 주소 -> 좌표 변환(Geocoding)
- 좌표 -> 정적 지도 이미지(Static Map) 바이트
- 네이버 지도 웹 링크 생성(키 불필요, 항상 동작)
키(.env: NAVER_MAP_CLIENT_ID / NAVER_MAP_CLIENT_SECRET)가 없거나 호출 실패 시
None을 반환해 기본 기능을 막지 않는다. (AI와 동일한 graceful degradation 패턴)
"""

from __future__ import annotations

import os
import urllib.parse

from dotenv import load_dotenv

load_dotenv()

_GEOCODE_URL = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
_STATIC_MAP_URL = "https://naveropenapi.apigw.ntruss.com/map-static/v2/raster"
_LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"


def _get(name: str) -> str | None:
    """환경변수 또는 Streamlit secrets에서 값을 읽는다."""
    val = os.getenv(name)
    if val:
        return val
    try:
        import streamlit as st  # noqa: WPS433

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # pragma: no cover
        pass
    return None


def _credentials() -> tuple[str | None, str | None]:
    return _get("NAVER_MAP_CLIENT_ID"), _get("NAVER_MAP_CLIENT_SECRET")


def is_available() -> bool:
    """Geocoding/Static Map 호출에 필요한 키가 모두 있는지 여부."""
    cid, secret = _credentials()
    return bool(cid and secret)


def _headers() -> dict:
    cid, secret = _credentials()
    return {
        "X-NCP-APIGW-API-KEY-ID": cid or "",
        "X-NCP-APIGW-API-KEY": secret or "",
    }


def geocode(query: str) -> dict | None:
    """
    주소/장소명을 좌표로 변환한다.
    반환: {"address": str, "lat": float, "lng": float} 또는 None.
    """
    if not query or not is_available():
        return None
    try:
        import requests

        resp = requests.get(
            _GEOCODE_URL, headers=_headers(), params={"query": query}, timeout=6,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        addresses = data.get("addresses") or []
        if not addresses:
            return None
        a = addresses[0]
        return {
            "address": a.get("roadAddress") or a.get("jibunAddress") or query,
            "lat": float(a["y"]),
            "lng": float(a["x"]),
        }
    except Exception:  # pragma: no cover - 외부 호출 실패 시 폴백
        return None


def static_map_bytes(lat, lng, width: int = 360, height: int = 200, level: int = 16) -> bytes | None:
    """좌표를 중심으로 마커가 찍힌 정적 지도 PNG 바이트를 반환한다(실패 시 None)."""
    if lat is None or lng is None or not is_available():
        return None
    try:
        import requests

        params = {
            "w": width, "h": height, "center": f"{lng},{lat}", "level": level,
            "markers": f"type:d|size:mid|pos:{lng} {lat}",
            "format": "png",
        }
        resp = requests.get(_STATIC_MAP_URL, headers=_headers(), params=params, timeout=6)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:  # pragma: no cover
        return None
    return None


def is_search_available() -> bool:
    """네이버 지역 검색(Developers Open API) 키가 있는지 여부."""
    return bool(_get("NAVER_SEARCH_CLIENT_ID") and _get("NAVER_SEARCH_CLIENT_SECRET"))


def _strip_tags(text: str) -> str:
    """검색 결과 제목의 <b></b> 등 태그를 제거한다."""
    import re
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _to_coord(value) -> float | None:
    """네이버 지역검색 mapx/mapy(정수, WGS84*1e7)를 경위도(float)로 변환한다."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    # 정수형 좌표는 1e7로 나눠 실제 경위도로 변환
    if abs(v) > 1000:
        v = v / 1e7
    return round(v, 7)


def search_local(query: str, display: int = 5, sort: str = "comment") -> list[dict]:
    """
    네이버 지역 검색으로 식당 후보를 가져온다.
    반환: [{"name","category","address","road_address","link","lat","lng"} ...]
    키가 없거나 실패하면 빈 리스트를 반환한다(기본 기능에 영향 없음).
    """
    if not query or not is_search_available():
        return []
    try:
        import requests

        headers = {
            "X-Naver-Client-Id": _get("NAVER_SEARCH_CLIENT_ID") or "",
            "X-Naver-Client-Secret": _get("NAVER_SEARCH_CLIENT_SECRET") or "",
        }
        params = {"query": query, "display": max(1, min(5, display)), "sort": sort}
        resp = requests.get(_LOCAL_SEARCH_URL, headers=headers, params=params, timeout=8)
        if resp.status_code != 200:
            return []
        items = resp.json().get("items", [])
        results = []
        for it in items:
            results.append({
                "name": _strip_tags(it.get("title")),
                "category": it.get("category"),
                "address": it.get("address"),
                "road_address": it.get("roadAddress"),
                "link": it.get("link"),
                "lat": _to_coord(it.get("mapy")),
                "lng": _to_coord(it.get("mapx")),
            })
        return results
    except Exception:  # pragma: no cover - 외부 호출 실패 폴백
        return []


def map_link(name: str, address: str | None = None) -> str:
    """
    네이버 지도 웹 검색 링크를 만든다(API 키 불필요, 항상 동작).
    식당명 + 주소로 검색해 길찾기/상세로 바로 이동할 수 있다.
    """
    query = name or ""
    if address:
        query = f"{name} {address}"
    return "https://map.naver.com/p/search/" + urllib.parse.quote(query)
