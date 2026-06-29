"""
services/ai_client.py
AI Provider 추상화 계층(OpenAI / Gemini / Claude / 기타).
- API Key는 .env 또는 Streamlit secrets에서 읽는다(코드에 하드코딩 금지).
- 호출 실패/패키지 미설치/키 없음 시 예외 대신 None을 반환해 기본 기능을 유지한다.
- is_available()로 AI 사용 가능 여부를 안전하게 확인할 수 있다.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# .env 로드 (있으면)
load_dotenv()

# Provider별 환경변수 키 이름
_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


def _get_secret(name: str) -> str | None:
    """환경변수 또는 Streamlit secrets에서 값을 읽는다."""
    value = os.getenv(name)
    if value:
        return value
    # Streamlit secrets는 import가 실패하거나 secrets가 없으면 조용히 무시
    try:
        import streamlit as st  # noqa: WPS433

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # pragma: no cover - secrets 미설정 등
        pass
    return None


def get_api_key(provider: str) -> str | None:
    """Provider에 해당하는 API Key를 반환한다(없으면 None)."""
    env_name = _ENV_KEYS.get(str(provider).lower())
    if not env_name:
        return None
    return _get_secret(env_name)


def is_available(settings: dict) -> bool:
    """
    AI 기능 사용 가능 여부.
    - 설정에서 ai_enabled가 켜져 있고
    - 해당 Provider의 API Key가 존재해야 한다.
    """
    if not settings.get("ai_enabled"):
        return False
    provider = settings.get("ai_provider", "openai")
    return bool(get_api_key(provider))


def chat(prompt: str, settings: dict, system: str | None = None,
         temperature: float = 0.4, max_tokens: int = 600) -> str | None:
    """
    설정된 Provider로 단발성 채팅 호출을 수행한다.
    실패 시(키 없음/패키지 없음/네트워크 오류 등) None을 반환한다 -> 기본 기능 유지.
    """
    provider = str(settings.get("ai_provider", "openai")).lower()
    model = settings.get("ai_model") or _default_model(provider)
    api_key = get_api_key(provider)
    if not api_key:
        return None

    try:
        if provider == "openai":
            return _call_openai(prompt, system, api_key, model, temperature, max_tokens)
        if provider == "gemini":
            return _call_gemini(prompt, system, api_key, model, temperature, max_tokens)
        if provider == "claude":
            return _call_claude(prompt, system, api_key, model, temperature, max_tokens)
    except Exception:  # pragma: no cover - 외부 호출 실패는 조용히 폴백
        return None
    return None


def _default_model(provider: str) -> str:
    return {
        "openai": "gpt-4o-mini",
        "gemini": "gemini-1.5-flash",
        "claude": "claude-3-5-haiku-latest",
    }.get(provider, "gpt-4o-mini")


def _call_openai(prompt, system, api_key, model, temperature, max_tokens):
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=model, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def _call_gemini(prompt, system, api_key, model, temperature, max_tokens):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system or None,
    )
    resp = gen_model.generate_content(
        prompt,
        generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
    )
    return resp.text


def _call_claude(prompt, system, api_key, model, temperature, max_tokens):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        system=system or "",
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    # content는 블록 리스트
    parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return "\n".join(parts) if parts else None
