# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - PDF 리포트 (reportlab).

한국어 출력을 위해 reportlab 내장 CID 폰트(HYSMyeongJo-Medium)를 사용한다.
별도 폰트 파일 없이 한글이 표시된다.
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from analyzers import statistics as stats
from utils import config


def _img(png_bytes, max_w_mm=170, max_h_mm=110):
    """PNG bytes → reportlab Image (비율 유지). 실패 시 None."""
    if not png_bytes:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        reader = ImageReader(BytesIO(png_bytes))
        iw, ih = reader.getSize()
        ratio = ih / iw if iw else 0.6
        w = max_w_mm * mm
        h = w * ratio
        if h > max_h_mm * mm:
            h = max_h_mm * mm
            w = h / ratio if ratio else max_w_mm * mm
        return Image(BytesIO(png_bytes), width=w, height=h)
    except Exception:
        return None

KOREAN_FONT = "HYSMyeongJo-Medium"


def _register_font() -> str:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(KOREAN_FONT))
        return KOREAN_FONT
    except Exception:
        return "Helvetica"


def _styles(font: str) -> dict:
    navy = colors.HexColor("#0D1B3D")
    blue = colors.HexColor("#1565E0")
    return {
        "title": ParagraphStyle("title", fontName=font, fontSize=18,
                                leading=24, spaceAfter=8, textColor=navy),
        "h2": ParagraphStyle("h2", fontName=font, fontSize=13, leading=18,
                             spaceBefore=12, spaceAfter=6, textColor=navy),
        "body": ParagraphStyle("body", fontName=font, fontSize=9.5,
                               leading=14),
        "small": ParagraphStyle("small", fontName=font, fontSize=8,
                                leading=11, textColor=colors.grey),
        # 표지 전용
        "cover_logo": ParagraphStyle("cover_logo", fontName=font, fontSize=46,
                                     leading=50, textColor=navy, spaceAfter=2),
        "cover_title": ParagraphStyle("cover_title", fontName=font,
                                      fontSize=17, leading=22, textColor=blue,
                                      spaceBefore=4, spaceAfter=20),
        "cover_line": ParagraphStyle("cover_line", fontName=font, fontSize=13,
                                     leading=20, textColor=navy),
    }


def _table(data: List[List[str]], font: str, col_widths=None) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D1B3D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E4E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F1F3F7")]),
    ]))
    return table


def _clip(text, n: int = 60) -> str:
    text = str(text or "")
    return text[:n] + ("…" if len(text) > n else "")


def export_pdf(results_df: pd.DataFrame, idea: dict,
               search_queries: List[str],
               timeline_lines: List[str],
               review: Optional[dict] = None,
               top_n: int = 10,
               file_path: Optional[str] = None,
               images: Optional[dict] = None) -> bytes:
    """분석 리포트 PDF 생성. bytes 반환 (file_path 지정 시 저장도).

    images: {"network": png bytes, "yearly": png bytes,
             "drawings": [(caption, png bytes), ...]} (선택)
    """
    images = images or {}
    font = _register_font()
    st = _styles(font)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    story = []

    # 표지/헤더
    story.append(Paragraph(
        'iP<super rise=10 size=24><font color="#1565E0">3</font></super>',
        st["cover_logo"]))
    story.append(Paragraph(
        'iP<super rise=6 size=11><font color="#1565E0">3</font></super>'
        ' Patent Review Report', st["cover_title"]))
    story.append(Paragraph("Intellectual Property", st["cover_line"]))
    story.append(Paragraph("Idea to Patent", st["cover_line"]))
    story.append(Paragraph("Intelligence Platform", st["cover_line"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}", st["small"]))
    story.append(Spacer(1, 8))

    # 1. 아이디어 개요
    story.append(Paragraph("1. 아이디어 개요", st["h2"]))
    story.append(Paragraph(f"아이디어명: {idea.get('title','-')}", st["body"]))
    story.append(Paragraph(f"설명: {idea.get('description','-')}", st["body"]))
    story.append(Paragraph(f"핵심 키워드: {idea.get('keywords','-')}", st["body"]))

    # 2. 검색식
    story.append(Paragraph("2. 사용한 검색식", st["h2"]))
    for q in (search_queries or ["-"]):
        story.append(Paragraph(f"• {q}", st["body"]))

    # 3. 유사특허 TOP N
    story.append(Paragraph(f"3. 유사특허 TOP {top_n}", st["h2"]))
    if results_df is not None and not results_df.empty:
        head = results_df.head(top_n)
        data = [["순위", "유사도", "특허명", "출원인", "연도", "상태"]]
        for _, p in head.iterrows():
            data.append([
                str(p.get("rank", "")), f"{p.get('total_score', 0):.0f}",
                _clip(p.get("title"), 38), _clip(p.get("applicant"), 14),
                str(p.get("application_year", "")), str(p.get("status", "")),
            ])
        story.append(_table(data, font,
                            col_widths=[12 * mm, 14 * mm, 80 * mm,
                                        32 * mm, 14 * mm, 14 * mm]))
    else:
        story.append(Paragraph("검색 결과 없음", st["body"]))

    # 4. 주요 통계
    story.append(Paragraph("4. 주요 통계", st["h2"]))
    if results_df is not None and not results_df.empty:
        cards = stats.summary_cards(results_df)
        story.append(Paragraph(
            f"총 {cards['total']}건 / 등록률 {cards['registered_rate']}% / "
            f"소멸률 {cards['expired_rate']}% / "
            f"최근 3년 증가율 {cards['recent_growth']}%", st["body"]))
        gc = stats.group_counts(results_df)
        data = [["기술군", "건수"]] + [
            [r["기술군"], str(r["건수"])] for _, r in gc.iterrows()]
        story.append(_table(data, font, col_widths=[60 * mm, 25 * mm]))
        chart = _img(images.get("yearly"), max_h_mm=70)
        if chart:
            story.append(Spacer(1, 6))
            story.append(Paragraph("연도별 출원 추이", st["small"]))
            story.append(chart)
    else:
        story.append(Paragraph("통계 데이터 없음", st["body"]))

    # 5. 기술발전도
    story.append(Paragraph("5. 기술발전도", st["h2"]))
    for line in (timeline_lines or ["-"]):
        clean = str(line).replace("**", "")
        story.append(Paragraph(f"• {clean}", st["body"]))
    netmap_img = _img(images.get("network"), max_h_mm=95)
    if netmap_img:
        story.append(Spacer(1, 6))
        story.append(Paragraph("시간축 네트워크맵", st["small"]))
        story.append(netmap_img)

    # 5-2. 대표도면
    drawings = images.get("drawings") or []
    if drawings:
        story.append(Paragraph("대표도면 (상위 유사특허)", st["h2"]))
        cells, captions = [], []
        for cap, png in drawings[:6]:
            di = _img(png, max_w_mm=52, max_h_mm=40)
            cells.append(di if di else Paragraph("-", st["small"]))
            captions.append(Paragraph(_clip(cap, 26), st["small"]))
        rows = [cells[i:i + 3] for i in range(0, len(cells), 3)]
        cap_rows = [captions[i:i + 3] for i in range(0, len(captions), 3)]
        interleaved = []
        for r, c in zip(rows, cap_rows):
            interleaved.append(r)
            interleaved.append(c)
        dtable = Table(interleaved, colWidths=[56 * mm] * 3)
        dtable.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story.append(dtable)

    # 6. AI 검토 요약
    story.append(Paragraph("6. AI 1차 검토 요약", st["h2"]))
    review = review or {}
    if review:
        for label, key in (("가장 유사한 특허", "most_risky_patents"),
                           ("공통 구성", "common_points"),
                           ("핵심 차별 포인트", "key_differentiators"),
                           ("회피설계 검토", "design_around_points")):
            items = review.get(key) or []
            if items:
                story.append(Paragraph(f"[{label}]", st["body"]))
                for item in items[:5]:
                    story.append(Paragraph(f"• {_clip(item, 110)}", st["body"]))
        if review.get("review_comment"):
            story.append(Spacer(1, 4))
            story.append(Paragraph(str(review["review_comment"]), st["body"]))
    else:
        story.append(Paragraph("AI 검토 미실행", st["body"]))

    # 7. 참고 문구
    story.append(Paragraph("7. 참고 문구", st["h2"]))
    story.append(Paragraph(
        "본 리포트는 GPC 내부 검토용 참고 자료입니다. AI 분석 결과는 1차 "
        "스크리닝 목적이며 최종 법률 판단이 아닙니다. 출원/실시 결정 전 "
        "변리사 등 전문가의 검토와 추가 선행기술 조사가 필요합니다.", st["small"]))

    doc.build(story)
    data = buf.getvalue()
    if file_path:
        Path(file_path).write_bytes(data)
    return data


def default_export_path(prefix: str = "gpc_ip_lens_report") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(config.EXPORTS_DIR / f"{prefix}_{ts}.pdf")
