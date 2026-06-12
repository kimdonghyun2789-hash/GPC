"""HTML 내부 검토 보고서 + Excel 결과 파일 생성."""
import html

import pandas as pd

from src import config
from src.differentiation import DIFF_FIELDS
from src.utils import now_display

_CSS = """
body { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
       background: #f6f7f9; color: #1f2937; margin: 0; padding: 32px; }
.container { max-width: 960px; margin: 0 auto; }
h1 { font-size: 24px; margin-bottom: 4px; }
.meta { color: #6b7280; font-size: 13px; margin-bottom: 24px; }
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
        padding: 20px 24px; margin-bottom: 16px; }
.card h2 { font-size: 16px; margin: 0 0 12px; color: #111827;
           border-bottom: 1px solid #f0f1f3; padding-bottom: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border: 1px solid #e5e7eb; padding: 6px 10px; text-align: left;
         vertical-align: top; }
th { background: #f9fafb; }
.chip { display: inline-block; background: #eef2ff; color: #3730a3;
        border-radius: 999px; padding: 2px 10px; margin: 2px; font-size: 12px; }
.kv { width: 100%; }
.kv th { width: 160px; }
.stat-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.stat { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
        padding: 12px 16px; min-width: 140px; }
.stat .label { font-size: 12px; color: #6b7280; }
.stat .value { font-size: 20px; font-weight: 700; }
.notice { background: #fffbeb; border: 1px solid #fde68a; color: #92400e;
          padding: 12px 16px; border-radius: 8px; font-size: 13px; }
"""


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _df_to_html(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p>해당 없음</p>"
    return df.to_html(index=False, escape=True, border=0)


def _chips(keywords) -> str:
    items = [k.strip() for k in str(keywords or "").split(",") if k.strip()]
    return "".join(f"<span class='chip'>{_esc(k)}</span>" for k in items)


def _candidates_df(candidates: list) -> pd.DataFrame:
    rows = [
        {
            "순위": p.get("rank", ""),
            "국가/출처": p.get("source", ""),
            "유사도 등급": p.get("grade", ""),
            "발명의 명칭": p.get("title", ""),
            "출원인": p.get("applicant", ""),
            "공개번호": p.get("pub_number", ""),
            "핵심 유사 키워드": p.get("matched_keywords", ""),
            "검토 필요 사유": p.get("review_reason", ""),
        }
        for p in candidates
    ]
    return pd.DataFrame(rows)


def _detail_card(patent: dict) -> str:
    fields = [
        ("발명의 명칭", patent.get("title")),
        ("출원인", patent.get("applicant")),
        ("국가/출처", patent.get("source")),
        ("출원번호", patent.get("app_number")),
        ("공개번호", patent.get("pub_number")),
        ("등록번호", patent.get("reg_number")),
        ("출원일", patent.get("app_date")),
        ("공개일", patent.get("pub_date")),
        ("IPC/CPC", patent.get("ipc")),
        ("권리상태", patent.get("status")),
        ("요약", patent.get("abstract")),
        ("핵심 유사 키워드", patent.get("matched_keywords")),
        ("검토 필요 사유", patent.get("review_reason")),
    ]
    rows = "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>"
        for label, value in fields
        if str(value or "").strip()
    )
    link = str(patent.get("link") or "").strip()
    if link:
        rows += (
            f"<tr><th>원문 열기</th><td><a href='{_esc(link)}' "
            f"target='_blank'>{_esc(link)}</a></td></tr>"
        )
    title = _esc(f"{patent.get('rank', '')}. {patent.get('title', '')}")
    return f"<h3 style='font-size:14px'>{title}</h3><table class='kv'>{rows}</table>"


def _statistics_html(stats: dict) -> str:
    if not stats:
        return "<p>해당 없음</p>"
    cards = (
        "<div class='stat-grid'>"
        f"<div class='stat'><div class='label'>검색 결과 총 건수</div>"
        f"<div class='value'>{stats.get('total_results', 0)}</div></div>"
        f"<div class='stat'><div class='label'>유사특허 후보 수</div>"
        f"<div class='value'>{stats.get('candidate_count', 0)}</div></div>"
        "</div>"
    )
    year_df = stats.get("year_df")
    if year_df is not None and not year_df.empty:
        year_df = year_df.reset_index()
    sections = [
        ("국가/출처별 건수", stats.get("country_df")),
        ("연도별 공개/출원 추이", year_df),
        ("주요 출원인 TOP 10", stats.get("applicant_df")),
        ("IPC/CPC TOP 10", stats.get("ipc_df")),
        ("유사도 등급 분포", stats.get("grade_df")),
    ]
    body = cards
    for label, df in sections:
        body += f"<h3 style='font-size:14px'>{_esc(label)}</h3>{_df_to_html(df)}"
    return body


def generate_report(
    idea: dict,
    candidates: list,
    stats: dict,
    claim_mapping_df: pd.DataFrame,
    diff_values: dict,
    favorites_df: pd.DataFrame,
    conclusion: str = "",
) -> tuple:
    """보고서(html)와 결과 파일(xlsx)을 생성하고 경로를 반환한다."""
    config.ensure_dirs()
    idea_id = idea["idea_id"]
    top_n = int(idea.get("top_n") or len(candidates) or 0)
    html_path = config.REPORTS_DIR / f"{idea_id}_report.html"
    xlsx_path = config.REPORTS_DIR / f"{idea_id}_results.xlsx"

    diff_rows = "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(diff_values.get(field, ''))}</td></tr>"
        for field, label in DIFF_FIELDS
    )
    details = "".join(_detail_card(p) for p in candidates[:5]) or "<p>해당 없음</p>"
    conclusion_text = conclusion or (
        "유사특허 검토 결과를 바탕으로 차별화 포인트를 구체화하고, "
        "필요 시 변리사 검토를 진행합니다."
    )

    sections = f"""
    <div class='card'><h2>1. 검토 개요</h2>
      <table class='kv'>
        <tr><th>작성일</th><td>{_esc(now_display())}</td></tr>
        <tr><th>검토상태</th><td>{_esc(idea.get('status', ''))}</td></tr>
      </table></div>
    <div class='card'><h2>2. Idea ID</h2><p><b>{_esc(idea_id)}</b></p></div>
    <div class='card'><h2>3. 입력 아이디어</h2><p>{_esc(idea.get('idea_text', ''))}</p></div>
    <div class='card'><h2>4. 핵심 키워드</h2>{_chips(idea.get('keywords', ''))}</div>
    <div class='card'><h2>5. 검색 조건</h2>
      <table class='kv'>
        <tr><th>검색 범위</th><td>{_esc(idea.get('search_scope', ''))}</td></tr>
        <tr><th>유사특허 표시 개수</th><td>{top_n}</td></tr>
      </table></div>
    <div class='card'><h2>6. 기본 통계</h2>{_statistics_html(stats)}</div>
    <div class='card'><h2>7. 유사특허 TOP {top_n}</h2>{_df_to_html(_candidates_df(candidates))}</div>
    <div class='card'><h2>8. 주요 특허 상세</h2>{details}</div>
    <div class='card'><h2>9. 청구항 키워드 매칭표</h2>
      {_df_to_html(claim_mapping_df)}
      <p style='color:#6b7280;font-size:12px'>{_esc(config.CLAIM_MAPPING_NOTICE)}</p></div>
    <div class='card'><h2>10. 차별화 포인트</h2><table class='kv'>{diff_rows}</table></div>
    <div class='card'><h2>11. 관심특허 및 검토의견</h2>{_df_to_html(favorites_df)}</div>
    <div class='card'><h2>12. 결론 및 다음 조치</h2><p>{_esc(conclusion_text)}</p></div>
    <div class='card'><h2>13. 주의사항</h2>
      <div class='notice'>{_esc(config.REPORT_DISCLAIMER)}</div></div>
    """

    document = f"""<!DOCTYPE html>
<html lang='ko'><head><meta charset='utf-8'>
<title>{_esc(idea_id)} 내부 검토 보고서</title>
<style>{_CSS}</style></head>
<body><div class='container'>
<h1>GPC IP Lens 내부 검토 보고서</h1>
<div class='meta'>{_esc(idea_id)} · {_esc(now_display())}</div>
{sections}
</div></body></html>"""

    html_path.write_text(document, encoding="utf-8")

    overview_df = pd.DataFrame(
        [
            ("Idea ID", idea_id),
            ("작성일", now_display()),
            ("입력 아이디어", idea.get("idea_text", "")),
            ("핵심 키워드", idea.get("keywords", "")),
            ("검색 범위", idea.get("search_scope", "")),
            ("유사특허 표시 개수", top_n),
            ("검색 결과 총 건수", stats.get("total_results", 0) if stats else 0),
            ("유사특허 후보 수", stats.get("candidate_count", 0) if stats else 0),
            ("검토상태", idea.get("status", "")),
            ("주의사항", config.REPORT_DISCLAIMER),
        ],
        columns=["항목", "내용"],
    )
    diff_df = pd.DataFrame(
        [(label, diff_values.get(field, "")) for field, label in DIFF_FIELDS],
        columns=["관점", "내용"],
    )

    with pd.ExcelWriter(xlsx_path) as writer:
        overview_df.to_excel(writer, sheet_name="검토개요", index=False)
        if stats:
            stats["country_df"].to_excel(writer, sheet_name="기본통계_국가", index=False)
            year_df = stats["year_df"].reset_index()
            year_df.to_excel(writer, sheet_name="기본통계_연도", index=False)
            stats["applicant_df"].to_excel(writer, sheet_name="기본통계_출원인", index=False)
            stats["ipc_df"].to_excel(writer, sheet_name="기본통계_IPC", index=False)
            stats["grade_df"].to_excel(writer, sheet_name="기본통계_등급", index=False)
        _candidates_df(candidates).to_excel(
            writer, sheet_name=f"유사특허 TOP {top_n}", index=False
        )
        if claim_mapping_df is not None and not claim_mapping_df.empty:
            claim_mapping_df.to_excel(writer, sheet_name="청구항 키워드 매칭", index=False)
        diff_df.to_excel(writer, sheet_name="차별화 포인트", index=False)
        if favorites_df is not None and not favorites_df.empty:
            favorites_df.to_excel(writer, sheet_name="관심특허", index=False)

    return html_path, xlsx_path
