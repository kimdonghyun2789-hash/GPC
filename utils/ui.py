"""
utils/ui.py
MML 전역 디자인 유틸리티.
- inject_global_css(): Pretendard 폰트 + 일관된 타이포/카드/버튼/추천카드 스타일
- logo_svg() / render_logo(): MML 로고(밥그릇 배지 + 워드마크)
- summary_chips(): 잘리지 않는 칩 형태의 요약 지표
- match_meta(): 추천점수를 사람이 이해하는 '매칭도' 라벨/밴드로 변환
컬러(PRD 19.2): 딥그린 #1F6F54 / 오렌지 #E8722B / 밝은회색 #F4F6F8
"""

from __future__ import annotations

import streamlit as st

# 브랜드 컬러 (로고 기준: 네이비 + 오렌지)
# 변수명은 호환을 위해 유지하되 값은 로고 네이비로 통일한다.
GREEN = "#16294F"        # 브랜드 네이비 (포인트)
GREEN_DARK = "#0E2044"   # 진한 네이비
ORANGE = "#FC7053"       # 로고 핀 오렌지
INK = "#1F2A37"
MUTE = "#6B7280"


# ------------------------------------------------------------------
# 로고
# ------------------------------------------------------------------
def logo_svg(width: int = 184, with_tagline: bool = True) -> str:
    """MML 로고 SVG 문자열(밥그릇 배지 + 워드마크 + 머물래 태그라인)."""
    height = round(width * 52 / 184)
    tagline = (
        f'<text x="64" y="44" font-family="Pretendard, sans-serif" font-size="10.5" '
        f'font-weight="700" fill="{ORANGE}" letter-spacing="6.5">머물래</text>'
        if with_tagline else ""
    )
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 184 52" fill="none"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="MML 머물래">
  <defs>
    <linearGradient id="mmlBadge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2F9072"/>
      <stop offset="1" stop-color="{GREEN_DARK}"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="48" height="48" rx="15" fill="url(#mmlBadge)"/>
  <!-- 김(스팀) -->
  <path d="M22 15 q-3.2 -3 0 -6.2" stroke="#FFFFFF" stroke-width="1.8"
        stroke-linecap="round" fill="none" opacity="0.8"/>
  <path d="M30 15 q3.2 -3 0 -6.2" stroke="#FFFFFF" stroke-width="1.8"
        stroke-linecap="round" fill="none" opacity="0.8"/>
  <!-- 밥(오렌지 봉우리) -->
  <path d="M16 26 Q26 16 36 26 Z" fill="{ORANGE}"/>
  <!-- 그릇 -->
  <ellipse cx="26" cy="26" rx="11.5" ry="2.4" fill="#FFFFFF"/>
  <path d="M15 26 L37 26 Q37 40 26 40 Q15 40 15 26 Z" fill="#FFFFFF"/>
  <path d="M19.5 33 Q26 36 32.5 33" stroke="#E4EDE9" stroke-width="1.4"
        fill="none" stroke-linecap="round"/>
  <!-- 워드마크 -->
  <text x="63" y="30" font-family="Pretendard, sans-serif" font-size="26"
        font-weight="800" fill="{GREEN}" letter-spacing="0.3">MML</text>
  {tagline}
</svg>
""".strip()


def render_logo(width: int = 184, with_tagline: bool = True) -> None:
    st.markdown(
        f'<div style="margin:2px 0 4px;">{logo_svg(width, with_tagline)}</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------
# 요약 칩
# ------------------------------------------------------------------
def page_header(title: str, subtitle: str | None = None) -> None:
    """모든 페이지에서 일관된 헤더(제목 + 부제)를 렌더링한다."""
    st.markdown(f'<div class="mml-ph">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="page-sub">{subtitle}</div>', unsafe_allow_html=True)


def section(title: str) -> None:
    """오렌지 액센트가 있는 섹션 제목."""
    st.markdown(f'<div class="sec-title">{title}</div>', unsafe_allow_html=True)


def summary_chips(items: list[tuple[str, str]]) -> None:
    """(라벨, 값) 리스트를 잘리지 않는 칩 묶음으로 렌더링한다."""
    chips = "".join(
        f'<div class="mml-chip"><span class="k">{k}</span>'
        f'<span class="v">{v}</span></div>'
        for k, v in items
    )
    st.markdown(f'<div class="mml-chips">{chips}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
# 매칭도(추천점수 -> 사람이 이해하는 라벨)
# ------------------------------------------------------------------
def match_meta(match: int) -> tuple[str, str]:
    """매칭도(%)를 (밴드 클래스, 라벨)로 변환한다."""
    if match >= 85:
        return "m-hi", "강력 추천"
    if match >= 70:
        return "m-mid", "추천"
    return "m-lo", "무난"


# ------------------------------------------------------------------
# 전역 CSS
# ------------------------------------------------------------------
def inject_global_css() -> None:
    st.markdown(
        f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"],
button, input, textarea, select {{
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
}}

h1 {{ font-size: 1.5rem !important; font-weight: 800 !important; color:{INK}; }}
h2 {{ font-size: 1.22rem !important; font-weight: 800 !important; color:{INK}; }}
h3 {{ font-size: 1.05rem !important; font-weight: 700 !important; color:{INK}; }}
.stApp p, .stApp li {{ font-size: 0.94rem; }}
.block-container {{ padding-top: 2rem; max-width: 800px; }}
.mml-ph {{ font-size:1.5rem; font-weight:800; color:{INK}; margin:0 0 1px;
           display:flex; align-items:center; gap:9px; }}
.mml-ph:before {{ content:""; width:5px; height:22px; border-radius:3px; background:{ORANGE}; }}
.page-sub {{ color:{MUTE}; font-size:0.92rem; margin:2px 0 12px; padding-left:14px; }}
.sec-title {{ font-size:1.02rem; font-weight:800; color:{INK}; margin:2px 0 8px;
              display:flex; align-items:center; gap:8px; }}
.sec-title:before {{ content:""; width:4px; height:15px; border-radius:3px; background:{ORANGE}; }}

/* 구분선을 가볍게 */
hr {{ margin:1.1rem 0 !important; border-color:#EEF1F4 !important; }}
[data-testid="stHeadingWithActionElements"] h2 {{ margin-top:0.2rem; }}

/* metric 보정 */
[data-testid="stMetricValue"] {{ font-size:1.35rem !important; font-weight:700 !important; }}
[data-testid="stMetricLabel"] p {{ font-size:0.8rem !important; color:{MUTE} !important; }}

/* 요약 칩 */
.mml-chips {{ display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 2px; }}
.mml-chip {{ background:#F4F6F8; border:1px solid #ECEFF3; border-radius:12px;
             padding:8px 13px; display:flex; flex-direction:column; min-width:78px; }}
.mml-chip .k {{ font-size:0.72rem; color:{MUTE}; line-height:1.2; }}
.mml-chip .v {{ font-size:1.0rem; font-weight:800; color:{INK}; line-height:1.35; }}

/* 버튼 */
.stButton > button {{ border-radius:12px; font-weight:700; padding:0.5rem 0.9rem;
                      border:1px solid #E3E7EC; transition:all .12s ease; }}
.stButton > button:hover {{ border-color:{ORANGE}; color:{ORANGE}; }}
.stButton > button[kind="primary"] {{ background:{ORANGE}; border:none; color:#fff;
                                       box-shadow:0 2px 8px rgba(232,114,43,0.26); }}
.stButton > button[kind="primary"]:hover {{ background:#d4631f; color:#fff; }}

/* 기본 컨테이너 카드 */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:16px !important;
    border-color:#ECEFF3 !important; box-shadow:0 1px 3px rgba(16,24,40,0.04);
    overflow:hidden; }}
[data-testid="stSidebar"] {{ background:#FFFFFF; border-right:1px solid #EEF1F4; }}
[data-testid="stProgress"] > div > div > div {{ background-color:{GREEN}; }}
[data-testid="stTextInput"] input, textarea {{ border-radius:10px !important; }}

/* ================= 추천 카드 ================= */
/* 카드 컨테이너 자체는 st.container(border=True). 아래는 내부 요소 스타일 */

/* 상단 헤더 띠: 카드 좌우/상단 패딩을 음수 마진으로 상쇄해 가장자리까지 채운다 */
.mml-head {{ margin:-1rem -1rem 0; padding:0.8rem 1rem 0.7rem;
    border-bottom:1px solid #EEF1F4; }}
.mml-head.r1 {{ background:#EEF1F8; border-bottom-color:#DCE3EF; }}
.mml-head.r2 {{ background:#FDF2EC; border-bottom-color:#F6E2D6; }}
.mml-head.r3 {{ background:#F5F6F8; border-bottom-color:#ECEEF1; }}
.mml-headrow {{ display:flex; align-items:center; gap:11px; }}
.mml-titlewrap {{ flex:1 1 auto; min-width:0; }}

.mml-ribbon {{ display:inline-block; color:#fff; font-size:0.66rem; font-weight:800;
    letter-spacing:0.5px; padding:3px 10px; border-radius:999px; margin-bottom:8px; background:{GREEN}; }}

.mml-rk {{ flex:0 0 auto; width:30px; height:30px; border-radius:9px; color:#fff;
    font-weight:800; font-size:0.95rem; display:flex; align-items:center; justify-content:center; }}
.r1 .mml-rk {{ background:{GREEN}; }} .r2 .mml-rk {{ background:{ORANGE}; }} .r3 .mml-rk {{ background:#9AA3AF; }}
.mml-name {{ font-size:1.16rem; font-weight:800; color:{INK}; line-height:1.22;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.mml-head.r1 .mml-name {{ font-size:1.3rem; }}
.mml-sub {{ font-size:0.82rem; color:{MUTE}; margin-top:2px; }}

.mml-match {{ flex:0 0 auto; text-align:center; border-radius:13px; padding:5px 11px; min-width:62px; }}
.mml-match .p {{ font-weight:800; font-size:1.05rem; line-height:1; }}
.mml-match .l {{ font-size:0.62rem; margin-top:2px; }}
.mml-match.m-hi  {{ background:#E9EDF6; }} .m-hi  .p {{ color:{GREEN}; }} .m-hi  .l {{ color:#5b6b8c; }}
.mml-match.m-mid {{ background:#FDF0E6; }} .m-mid .p {{ color:{ORANGE}; }} .m-mid .l {{ color:#B5763F; }}
.mml-match.m-lo  {{ background:#F1F3F6; }} .m-lo  .p {{ color:#6B7280; }} .m-lo  .l {{ color:#9AA3AF; }}

.mml-meta {{ display:flex; flex-wrap:wrap; align-items:center; row-gap:4px; margin:13px 0 9px;
    font-size:0.9rem; color:#374151; }}
.mml-meta span {{ white-space:nowrap; }}
.mml-meta .sep {{ color:#D3D8E0; margin:0 9px; }}
.mml-meta b {{ font-weight:700; color:{INK}; }}
.mml-bdot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; vertical-align:1px; }}

.mml-why {{ font-size:0.9rem; line-height:1.45; color:#33404F; background:#F7F9FB;
    border:1px solid #EEF2F6; border-radius:11px; padding:9px 13px; margin:0 0 9px; }}
.mml-head.r1 ~ .mml-why, .mml-why {{ }}
.mml-why b {{ color:{GREEN_DARK}; font-weight:700; }}

.mml-sublog {{ font-size:0.78rem; color:#9AA3AF; margin:0 0 12px; }}

.mml-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin:0 0 9px; }}
.mml-tag {{ font-size:0.74rem; font-weight:600; color:{GREEN_DARK}; background:#EEF1F8;
    border:1px solid #DDE3EF; border-radius:999px; padding:2px 9px; }}
.mml-warn {{ display:inline-block; font-size:0.72rem; font-weight:700; color:#B5763F;
    background:#FDF0E6; border:1px solid #F6E0D2; border-radius:999px; padding:1px 9px; margin-left:6px; }}

.mml-oneliner {{ background:#EEF1F8; border:1px solid #DDE3EF; border-radius:12px;
    padding:9px 13px; margin:0 0 12px; font-size:0.92rem; font-weight:600; color:{GREEN_DARK}; }}
</style>
""",
        unsafe_allow_html=True,
    )
