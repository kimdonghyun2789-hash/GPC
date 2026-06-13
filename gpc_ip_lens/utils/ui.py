# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - UI 디자인 시스템 (최종 로고 PNG 기준).

브랜드: iP³ 로고(assets/brand/ip3-logo.png) · 딥네이비 사이드바 · 블루 포인트.
표현(스타일)만 담당하며 기능/로직과 무관하다.
"""
import base64
import html
import io
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------- 브랜드 팔레트
NAVY = "#0A1F44"         # Deep Navy (사이드바)
DARK_BLUE = "#013A9E"    # Dark Blue
PRIMARY = "#0057FF"      # Primary Blue (주요 버튼)
BRIGHT = "#2F7CFF"       # Bright Blue (활성·강조·링크)
LIGHT_BLUE = "#A9D0FF"   # Light Blue
SLATE = "#475569"        # Slate Gray (보조 텍스트)
LIGHT_GRAY = "#F2F4F7"   # Light Gray (배경/구분선)
WHITE = "#FFFFFF"

BG = "#F2F4F7"           # 콘텐츠 배경
SURFACE = "#FFFFFF"      # 카드 배경
INK = "#0F2147"          # 본문 강조
MUTED = "#475569"        # 보조 텍스트
FAINT = "#8A97AC"        # 3차 텍스트
BORDER = "#E4E8F0"       # 테두리
ACCENT_SOFT = "#E7F0FF"  # 연한 블루 배경

# 로고 에셋 경로 (개발/배포 모두 대응)
_LOGO_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "assets" / "brand" / "ip3-logo.png",
]
try:
    from utils import config as _cfg
    _LOGO_CANDIDATES.append(_cfg.BASE_DIR / "assets" / "brand" / "ip3-logo.png")
    import sys as _sys
    if hasattr(_sys, "_MEIPASS"):
        _LOGO_CANDIDATES.append(
            Path(_sys._MEIPASS) / "assets" / "brand" / "ip3-logo.png")
except Exception:
    pass

# 기술군 색 (블루 계열 카테고리 · network_map 공용)
GROUP_COLORS = {
    "접합부": "#0057FF", "전단키": "#2F7CFF", "생산방법": "#1FA59A",
    "몰드": "#6C63D6", "배수": "#2B6CD4", "방수": "#5B86B5",
    "품질관리": "#9A5FC0", "유지관리": "#475569", "센서": "#1F9E72",
    "시공장비": "#1796B0", "기타": "#8A97AC",
}

# 유사도 등급 (bg, fg)
GRADE_STYLE = {
    "고유사/주의": ("#FCE7E5", "#C0392B"),
    "유사": ("#FFF0DA", "#B5701A"),
    "관련 있음": ("#E3EDFF", "#0057FF"),
    "낮음": ("#EDEFF4", "#475569"),
}

# 특허 상태 (bg, fg)
STATUS_STYLE = {
    "등록": ("#E1F2E8", "#2C8A4E"),
    "공개": ("#E3EDFF", "#0057FF"),
    "소멸": ("#EDEFF4", "#6B7686"),
    "거절": ("#FCE7E5", "#C0392B"),
    "취하": ("#EDEFF4", "#6B7686"),
    "포기": ("#EDEFF4", "#6B7686"),
}

SANS = ("'Pretendard','Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',"
        "'Malgun Gothic','Apple SD Gothic Neo',sans-serif")

_logo_cache = {}


def _logo_uri(height: int = 96):
    """로고 PNG를 height(px)로 축소해 base64 data URI 로 반환. 없으면 None."""
    if height in _logo_cache:
        return _logo_cache[height]
    uri = None
    for path in _LOGO_CANDIDATES:
        try:
            if path.exists():
                from PIL import Image
                im = Image.open(path).convert("RGBA")
                ratio = height / im.height
                im = im.resize((int(im.width * ratio), height), Image.LANCZOS)
                buf = io.BytesIO(); im.save(buf, format="PNG")
                uri = "data:image/png;base64," + \
                    base64.b64encode(buf.getvalue()).decode()
                break
        except Exception:
            continue
    _logo_cache[height] = uri
    return uri


def inject_theme() -> None:
    st.markdown(
        f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@latest/dist/web/static/pretendard.min.css');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {{
  --navy:{NAVY}; --primary:{PRIMARY}; --bright:{BRIGHT}; --slate:{SLATE};
  --bg:{BG}; --surface:{SURFACE}; --ink:{INK}; --muted:{MUTED};
  --faint:{FAINT}; --border:{BORDER}; --accent-soft:{ACCENT_SOFT};
}}

html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {{
  font-family:{SANS}; color:var(--ink); -webkit-font-smoothing:antialiased;
}}
.stApp {{ background:var(--bg); }}
[data-testid="stMainBlockContainer"] {{
  padding-top:2rem; padding-bottom:4rem; max-width:1320px;
}}
[data-testid="stHeader"] {{ background:transparent; }}
h1,h2,h3,h4 {{ font-family:{SANS}; letter-spacing:-.015em; color:var(--ink);
  font-weight:700; }}

/* ---------- 페이지 헤더 ---------- */
.gpc-page-head {{ margin:0 0 1.5rem; padding-bottom:1rem;
  border-bottom:1px solid var(--border); }}
.gpc-page-head .t {{ font-size:1.55rem; font-weight:800; color:var(--ink);
  letter-spacing:-.02em; line-height:1.2; }}
.gpc-page-head .s {{ font-size:.88rem; color:var(--muted); margin-top:.35rem;
  max-width:72ch; line-height:1.5; }}

/* ---------- 지표 카드 ---------- */
[data-testid="stMetric"] {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:1.1rem 1.25rem;
  box-shadow:0 1px 2px rgba(10,31,68,.05);
}}
[data-testid="stMetricLabel"] p {{ color:var(--muted); font-size:.8rem;
  font-weight:500; }}
[data-testid="stMetricValue"] {{ color:var(--navy); font-weight:800;
  font-size:1.8rem; letter-spacing:-.02em; }}

/* ---------- 버튼 ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius:10px; font-weight:600; font-size:.88rem;
  border:1px solid var(--border); background:var(--surface); color:var(--ink);
  padding:.5rem 1.05rem; min-height:2.5rem; transition:all .13s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {{
  border-color:var(--primary); color:var(--primary); background:var(--accent-soft);
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background:var(--primary); border:1px solid var(--primary); color:#fff;
  box-shadow:0 2px 6px rgba(0,87,255,.25);
}}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {{
  background:{DARK_BLUE}; border-color:{DARK_BLUE}; color:#fff;
}}

/* ---------- 입력 위젯 ---------- */
.stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {{
  border-radius:10px; border-color:var(--border);
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
  border-color:var(--primary); box-shadow:0 0 0 2px var(--accent-soft);
}}

/* ---------- 탭 ---------- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap:1.6rem; border-bottom:1px solid var(--border);
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  padding:.6rem .1rem; font-weight:600; font-size:.92rem; color:var(--muted);
}}
[data-testid="stTabs"] [aria-selected="true"] {{
  color:var(--bright); border-bottom-color:var(--bright) !important;
}}

/* ---------- 컨테이너 ---------- */
[data-testid="stExpander"] {{
  border:1px solid var(--border); border-radius:12px; background:var(--surface);
}}
[data-testid="stExpander"] summary {{ font-weight:500; }}
[data-testid="stDataFrame"] {{
  border:1px solid var(--border); border-radius:12px; overflow:hidden;
}}
[data-testid="stAlert"] {{ border-radius:10px; border:1px solid var(--border); }}
hr {{ border-color:var(--border); margin:1.4rem 0; }}
a, a:visited {{ color:var(--bright); }}

/* ---------- 사이드바 (Deep Navy) ---------- */
section[data-testid="stSidebar"] {{
  background:{NAVY}; border-right:1px solid rgba(255,255,255,.06);
}}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
  padding:1.4rem .85rem;
}}
section[data-testid="stSidebar"] * {{ color:#C7D2E6; }}
.gpc-brand {{ padding:.2rem .3rem 1.1rem; margin-bottom:.6rem;
  border-bottom:1px solid rgba(255,255,255,.1); text-align:center; }}
.gpc-brand .chip {{ display:inline-flex; align-items:center; justify-content:center;
  background:#fff; border-radius:16px; padding:12px 16px;
  box-shadow:0 4px 14px rgba(0,0,0,.18); }}
.gpc-brand .chip img {{ height:54px; width:auto; object-fit:contain; display:block; }}
.gpc-brand .k {{ font-size:.66rem; color:#8FA0C0 !important; letter-spacing:.14em;
  text-transform:uppercase; margin-top:.7rem; }}

/* 네비게이션(라디오) */
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap:3px; margin-top:.4rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
  border-radius:9px; padding:.55rem .8rem; margin:0; cursor:pointer;
  font-size:.92rem; font-weight:500; color:#AEBAD2 !important;
  transition:all .12s ease; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
  background:rgba(255,255,255,.06); color:#FFFFFF !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
  background:{BRIGHT}; color:#FFFFFF !important; font-weight:700;
  box-shadow:0 2px 8px rgba(47,124,255,.4);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) * {{
  color:#FFFFFF !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {{
  display:none;
}}
section[data-testid="stSidebar"] [data-testid="stMetric"] {{
  background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08);
}}
section[data-testid="stSidebar"] [data-testid="stMetricValue"] {{ color:#FFFFFF; }}
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] p {{ color:#9AA8C6; }}

/* ---------- 상단 헤더 ---------- */
.ip3-topbar {{ display:flex; align-items:center; gap:14px;
  padding:.1rem .1rem 1rem; margin-bottom:1.4rem;
  border-bottom:1px solid var(--border); }}
.ip3-topbar img {{ height:34px; width:auto; object-fit:contain; }}
.ip3-topbar .tag {{ font-size:.8rem; color:var(--muted); line-height:1.35;
  border-left:2px solid var(--border); padding-left:14px; }}
.ip3-topbar .tag b {{ color:var(--primary); font-weight:600; }}
.ip3-word {{ font-family:'Inter',{SANS}; font-weight:800; letter-spacing:-.03em;
  color:var(--navy); }}
.ip3-word sup {{ font-size:.5em; color:var(--bright); }}

/* ---------- 배지 / 카드 ---------- */
.gpc-badge {{ display:inline-block; padding:2px 9px; border-radius:6px;
  font-size:.74rem; font-weight:600; line-height:1.6; white-space:nowrap;
  max-width:100%; overflow:hidden; text-overflow:ellipsis; vertical-align:middle; }}
.gpc-card {{ background:var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:1rem 1.15rem; height:100%;
  box-shadow:0 1px 2px rgba(10,31,68,.05);
  overflow-wrap:anywhere; word-break:break-word; }}
.gpc-card .ct {{ font-size:.68rem; color:var(--faint); font-weight:700;
  letter-spacing:.08em; text-transform:uppercase; margin-bottom:.45rem; }}
.gpc-card .cv {{ font-size:.88rem; color:var(--ink); line-height:1.6; }}
</style>
        """,
        unsafe_allow_html=True,
    )


def _text_wordmark(color="#FFFFFF") -> str:
    return (f'<span class="ip3-word" style="color:{color};font-size:1.6rem">'
            f'iP<sup>3</sup></span>')


def sidebar_brand() -> None:
    """사이드바 상단: 로고 PNG(흰 칩) + IP Cube 캡션."""
    uri = _logo_uri(108)
    inner = (f'<img src="{uri}" alt="IP3"/>' if uri
             else _text_wordmark(NAVY))
    st.markdown(
        f'<div class="gpc-brand"><span class="chip">{inner}</span>'
        f'<div class="k">IP Cube · Patent Intelligence</div></div>',
        unsafe_allow_html=True)


def app_header() -> None:
    """메인 영역 상단 헤더: 로고 + 태그라인."""
    uri = _logo_uri(72)
    logo = (f'<img src="{uri}" alt="IP3"/>' if uri else _text_wordmark(NAVY))
    st.markdown(
        f'<div class="ip3-topbar">{logo}'
        f'<div class="tag"><b>Intellectual Property</b> · '
        f'<b>Idea to Patent</b> · <b>Intelligence Platform</b></div></div>',
        unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="s">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="gpc-page-head"><div class="t">{html.escape(title)}</div>'
        f'{sub}</div>',
        unsafe_allow_html=True)


def _badge(text: str, bg: str, fg: str) -> str:
    return (f'<span class="gpc-badge" style="background:{bg};color:{fg}">'
            f'{html.escape(str(text))}</span>')


def grade_badge(grade: str) -> str:
    bg, fg = GRADE_STYLE.get(grade, ("#EDEFF4", "#475569"))
    return _badge(grade, bg, fg)


def status_badge(status: str) -> str:
    bg, fg = STATUS_STYLE.get(status, ("#EDEFF4", "#475569"))
    return _badge(status, bg, fg)


def _tint(hex_color: str, amt: float = 0.88) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amt); g = int(g + (255 - g) * amt)
    b = int(b + (255 - b) * amt)
    return f"#{r:02X}{g:02X}{b:02X}"


def group_badge(group: str) -> str:
    color = GROUP_COLORS.get(group, "#8A97AC")
    return _badge(group, _tint(color), color)


def info_card(title: str, value_html: str) -> str:
    return (f'<div class="gpc-card"><div class="ct">{html.escape(title)}</div>'
            f'<div class="cv">{value_html}</div></div>')
