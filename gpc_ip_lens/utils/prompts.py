# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 프롬프트 로더.

AI 프롬프트를 코드에서 분리해 prompts/*.md 로 관리한다. 파일이 없거나
포맷 오류가 나면 None 을 반환하여 호출부가 인라인 fallback 을 쓰게 한다.
"""
from utils import config

_PROMPT_DIR = config.BASE_DIR / "prompts"
_cache = {}


def _read(name: str):
    if name in _cache:
        return _cache[name]
    path = _PROMPT_DIR / f"{name}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = None
    _cache[name] = text
    return text


def render(name: str, **kwargs):
    """prompts/<name>.md 를 읽어 {placeholder} 치환. 실패 시 None."""
    template = _read(name)
    if not template:
        return None
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return None
