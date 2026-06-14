# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 파일 기반 JSON 캐시 (KIPRIS 상세정보/도면 캐싱용)."""
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from utils import config


def _cache_path(key: str) -> Path:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return config.CACHE_DIR / f"{digest}.json"


def cache_get(key: str) -> Optional[Any]:
    path = _cache_path(key)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None


def cache_set(key: str, value: Any) -> None:
    try:
        _cache_path(key).write_text(
            json.dumps(value, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except OSError:
        pass


def clear_cache() -> int:
    """캐시 파일 전체 삭제. 삭제한 파일 수 반환."""
    count = 0
    for f in config.CACHE_DIR.glob("*.json"):
        try:
            f.unlink()
            count += 1
        except OSError:
            pass
    return count
