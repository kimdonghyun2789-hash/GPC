# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 그래프/네트워크맵 이미지 내보내기.

PNG 변환은 kaleido 가 필요하다. kaleido 가 없거나 실패하면
인터랙티브 HTML 로 대신 내보낸다 (브라우저에서 열람/캡처 가능).
"""
from datetime import datetime
from typing import Optional, Tuple

import plotly.graph_objects as go

from utils import config


def figure_to_png(fig: go.Figure) -> Optional[bytes]:
    """Plotly Figure → PNG bytes. kaleido 미설치 시 None."""
    try:
        return fig.to_image(format="png", width=1400, height=800, scale=2)
    except Exception:
        return None


def figure_to_html(fig: go.Figure) -> bytes:
    return fig.to_html(include_plotlyjs="cdn").encode("utf-8")


def export_figure(fig: go.Figure, name: str) -> Tuple[bytes, str, str]:
    """Figure 를 (bytes, 파일명, mime) 로 반환. PNG 우선, 실패 시 HTML."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    png = figure_to_png(fig)
    if png is not None:
        return png, f"{name}_{ts}.png", "image/png"
    return figure_to_html(fig), f"{name}_{ts}.html", "text/html"


def save_figure(fig: go.Figure, name: str) -> str:
    """data/exports/ 에 저장하고 경로 반환."""
    data, filename, _ = export_figure(fig, name)
    path = config.EXPORTS_DIR / filename
    path.write_bytes(data)
    return str(path)
