"""
utils/ui.py
MML 전역 디자인 유틸리티.
- inject_global_css(): Pretendard 폰트 + 일관된 타이포/카드/버튼 스타일 주입
- logo_svg(): MML 로고(밥그릇 아이콘 + 워드마크) SVG 마크업 생성
- render_logo(): 사이드바/헤더에 로고 렌더링
- summary_chips(): 잘리지 않는 칩(chip) 형태의 요약 지표 렌더링
컬러 컨셉(PRD 19.2): 딥그린(#1F6F54) / 오렌지(#E8722B) / 밝은회색(#F4F6F8)
"""

from __future__ import annotations

import streamlit as st

GREEN = "#1F6F54"
GREEN_DARK = "#155740"
ORANGE = "#E8722B"
INK = "#1F2A37"
MUTE = "#6B7280"


def logo_svg(width: int = 176, with_tagline: bool = True) -> str:
    """MML 로고 SVG 문자열을 반환한다(밥그릇+김 아이콘 + 워드마크)."""
    height = round(width * 56 / 176)
    tagline = (
        f'<text x="62" y="47" font-family="Pretendard, sans-serif" font-size="11.5" '
        f'font-weight="700" fill="{ORANGE}" letter-spacing="7">머물래</text>'
        if with_tagline else ""
    )
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 176 56" fill="none"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="MML 머물래">
  <defs>
    <linearGradient id="mmlBadge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2E8B6E"/>
      <stop offset="1" stop-color="{GREEN_DARK}"/>
    </linearGradient>
  </defs>
  <!-- 배지 -->
  <rect x="3" y="4" width="48" height="48" rx="14" fill="url(#mmlBadge)"/>
  <!-- 김(스팀) -->
  <path d="M21 16 q-3 -3 0 -6" stroke="#FFFFFF" stroke-width="2"
        stroke-linecap="round" fill="none" opacity="0.85"/>
  <path d="M27 16 q3 -3 0 -6" stroke="#FFFFFF" stroke-width="2"
        stroke-linecap="round" fill="none" opacity="0.85"/>
  <!-- 밥(오렌지 봉우리) -->
  <path d="M16 27 Q27 15 38 27 Z" fill="{ORANGE}"/>
  <!-- 그릇 -->
  <ellipse cx="27" cy="27" rx="12" ry="2.6" fill="#FFFFFF"/>
  <path d="M15 27 L39 27 Q39 41 27 41 Q15 41 15 27 Z" fill="#FFFFFF"/>
  <!-- 워드마크 -->
  <text x="61" y="31" font-family="Pretendard, sans-serif" font-size="27"
        font-weight="800" fill="{GREEN}" letter-spacing="0.5">MML</text>
  {tagline}
</svg>
""".strip()


def render_logo(width: int = 176, with_tagline: bool = True) -> None:
    """로고를 렌더링한다."""
    st.markdown(
        f'<div style="margin:2px 0 6px;">{logo_svg(width, with_tagline)}</div>',
        unsafe_allow_html=True,
    )


def summary_chips(items: list[tuple[str, str]]) -> None:
    """
    (라벨, 값) 튜플 리스트를 받아 잘리지 않는 칩 묶음으로 렌더링한다.
    st.metric의 글자 잘림 문제를 대체한다.
    """
    chips = "".join(
        f'<div class="mml-chip"><span class="k">{k}</span>'
        f'<span class="v">{v}</span></div>'
        for k, v in items
    )
    st.markdown(f'<div class="mml-chips">{chips}</div>', unsafe_allow_html=True)


def inject_global_css() -> None:
    """전역 CSS를 주입한다(앱 진입점에서 1회 호출)."""
    st.markdown(
        f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

/* ---- 기본 폰트 ---- */
html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"],
button, input, textarea, select {{
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
}}

/* ---- 제목 크기 정리 ---- */
h1 {{ font-size: 1.55rem !important; font-weight: 800 !important; color: {INK}; }}
h2 {{ font-size: 1.25rem !important; font-weight: 700 !important; color: {INK}; }}
h3 {{ font-size: 1.08rem !important; font-weight: 700 !important; color: {INK}; }}
.stApp p, .stApp li {{ font-size: 0.95rem; }}

/* ---- 본문 폭 약간 여유 ---- */
.block-container {{ padding-top: 2.2rem; max-width: 820px; }}

/* ---- st.metric 글자 잘림/과대 크기 보정 ---- */
[data-testid="stMetricValue"] {{ font-size: 1.35rem !important; font-weight: 700 !important; }}
[data-testid="stMetricLabel"] p {{ font-size: 0.8rem !important; color: {MUTE} !important; }}

/* ---- 요약 칩 ---- */
.mml-chips {{ display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 2px; }}
.mml-chip {{
    background:{'#F4F6F8'}; border:1px solid #ECEFF3; border-radius:12px;
    padding:8px 13px; display:flex; flex-direction:column; min-width:80px;
}}
.mml-chip .k {{ font-size:0.72rem; color:{MUTE}; line-height:1.2; }}
.mml-chip .v {{ font-size:1.0rem; font-weight:800; color:{INK}; line-height:1.35; }}

/* ---- 버튼 ---- */
.stButton > button {{
    border-radius: 12px; font-weight: 700; padding: 0.5rem 0.9rem;
    border: 1px solid #E3E7EC; transition: all .12s ease;
}}
.stButton > button:hover {{ border-color: {ORANGE}; color: {ORANGE}; }}
.stButton > button[kind="primary"] {{
    background: {ORANGE}; border: none; color: #fff;
    box-shadow: 0 2px 8px rgba(232,114,43,0.28);
}}
.stButton > button[kind="primary"]:hover {{ background: #d4631f; color:#fff; }}

/* ---- 카드(테두리 컨테이너) ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 16px !important;
    border-color: #ECEFF3 !important;
    box-shadow: 0 1px 3px rgba(16,24,40,0.04);
}}

/* ---- 사이드바 ---- */
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid #EEF1F4; }}
[data-testid="stSidebarNav"] a {{ border-radius: 10px; }}

/* ---- 입력창 ---- */
[data-testid="stTextInput"] input, textarea {{ border-radius: 10px !important; }}

/* ---- 진행바 색상 ---- */
[data-testid="stProgress"] > div > div > div {{ background-color: {GREEN}; }}

/* ---- 추천 카드 헤더(순위 배지 + 제목 + 점수) ---- */
.mml-card-head {{ display:flex; align-items:center; gap:12px; margin-bottom:4px; }}
.mml-rank {{
    flex:0 0 auto; width:36px; height:36px; border-radius:11px; display:flex;
    align-items:center; justify-content:center; font-weight:800; font-size:1.05rem; color:#fff;
}}
.mml-rank.r1 {{ background:{GREEN}; }}
.mml-rank.r2 {{ background:{ORANGE}; }}
.mml-rank.r3 {{ background:#8A94A6; }}
.mml-card-title {{ flex:1 1 auto; min-width:0; }}
.mml-card-title .name {{ font-size:1.12rem; font-weight:800; color:{INK}; line-height:1.25; }}
.mml-card-title .sub {{ font-size:0.82rem; color:{MUTE}; }}
.mml-score {{ flex:0 0 auto; text-align:right; line-height:1.1; }}
.mml-score .s {{ display:block; font-size:1.2rem; font-weight:800; color:{GREEN}; }}
.mml-score .l {{ font-size:0.66rem; color:#9AA3AF; }}

/* ---- 정보 라인 / 사유 배지 ---- */
.mml-info {{ font-size:0.9rem; color:{INK}; margin:2px 0; }}
.mml-info .dot {{ color:#C7CDD6; margin:0 5px; }}
.mml-reason {{
    display:inline-block; background:#F1F7F4; color:{GREEN_DARK}; border:1px solid #DDEBE4;
    border-radius:999px; padding:2px 10px; font-size:0.78rem; margin:3px 5px 0 0;
}}
</style>
""",
        unsafe_allow_html=True,
    )
