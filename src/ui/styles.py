"""내부 업무툴 스타일 — 밝은 배경, 카드형 레이아웃, 넉넉한 여백."""
import streamlit as st

_APP_CSS = """
<style>
.stApp { background-color: #f6f7f9; }

section[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e5e7eb;
}

h1 { font-size: 1.7rem !important; letter-spacing: -0.02em; }
h2, h3 { letter-spacing: -0.01em; }

div[data-testid="stTextArea"] textarea { font-size: 1rem; }

.stButton > button[kind="primary"] {
    background-color: #2563eb;
    border: none;
    padding: 0.6rem 1.4rem;
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover { background-color: #1d4ed8; }

div[data-testid="stExpander"] {
    background: #ffffff;
    border-radius: 10px;
}

.gpc-chip {
    display: inline-block;
    background: #eef2ff;
    color: #3730a3;
    border-radius: 999px;
    padding: 3px 12px;
    margin: 3px 4px 3px 0;
    font-size: 0.8rem;
    font-weight: 500;
}

.gpc-badge {
    display: inline-block;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 600;
}
.gpc-badge-kr { background: #ecfdf5; color: #047857; }
.gpc-badge-foreign { background: #eff6ff; color: #1d4ed8; }

.gpc-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
}
.gpc-stat-label { font-size: 0.78rem; color: #6b7280; }
.gpc-stat-value { font-size: 1.5rem; font-weight: 700; color: #111827; }

/* 핸드폰 화면 최적화 */
@media (max-width: 640px) {
    .block-container {
        padding: 1rem 0.9rem 3rem 0.9rem !important;
    }
    h1 { font-size: 1.35rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 1rem !important; }
    .gpc-stat-value { font-size: 1.15rem; }
    .gpc-card { padding: 0.75rem 0.9rem; }
    .stButton > button[kind="primary"] { width: 100%; }
    div[data-testid="stDownloadButton"] > button { width: 100%; }
}
</style>
"""


def apply_styles() -> None:
    st.markdown(_APP_CSS, unsafe_allow_html=True)
