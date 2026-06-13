# -*- coding: utf-8 -*-
"""GPC IP Lens - 시간축 네트워크맵 (Plotly + networkx).

배치 원칙:
- X축 = 출원연도, Y축 = 기술군
- 노드 = 특허 (크기=종합 유사도, 색=기술군, 테두리=상태)
- 별표 노드 = 내 아이디어
- 선 = 아이디어-특허 유사도 / 특허-특허 벡터 유사도
"""
from typing import List, Optional

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from analyzers.classifier import TECH_GROUPS
from analyzers.similarity import pairwise_vector_matrix

GROUP_COLORS = {
    "접합부": "#1f77b4", "전단키": "#ff7f0e", "생산방법": "#2ca02c",
    "몰드": "#d62728", "배수": "#9467bd", "방수": "#8c564b",
    "품질관리": "#e377c2", "유지관리": "#7f7f7f", "센서": "#bcbd22",
    "시공장비": "#17becf", "기타": "#aec7e8",
}

STATUS_BORDER = {"등록": "#2ca02c", "공개": "#1f77b4", "소멸": "#999999",
                 "거절": "#d62728", "취하": "#999999", "포기": "#999999"}


def build_graph(df: pd.DataFrame, idea_title: str,
                similarity_threshold: float = 40.0,
                patent_edge_threshold: float = 0.45) -> nx.Graph:
    """아이디어/특허/기술군 노드와 유사도 엣지로 그래프 구성."""
    g = nx.Graph()
    g.add_node("IDEA", kind="idea", label=idea_title or "내 아이디어")
    for _, p in df.iterrows():
        node_id = p["application_no"]
        g.add_node(node_id, kind="patent", label=p["title"],
                   year=int(p["application_year"]),
                   group=p["technology_group"], status=p["status"],
                   applicant=p["applicant"], total_score=float(p["total_score"]))
        # 아이디어 — 특허: 종합 유사도
        if float(p["total_score"]) >= similarity_threshold:
            g.add_edge("IDEA", node_id, weight=float(p["total_score"]) / 100,
                       kind="idea-patent")
        # 특허 — 기술군 (분류 관계는 그래프 속성으로만 유지)
    # 특허 — 특허: 벡터 유사도
    if "comparison_text" in df.columns and len(df) >= 2:
        matrix = pairwise_vector_matrix(df["comparison_text"].tolist())
        ids = df["application_no"].tolist()
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if matrix[i, j] >= patent_edge_threshold:
                    g.add_edge(ids[i], ids[j], weight=float(matrix[i, j]),
                               kind="patent-patent")
    return g


def _node_positions(df: pd.DataFrame, groups: List[str], seed: int = 42):
    """X=연도, Y=기술군 인덱스(+지터) 좌표 계산."""
    rng = np.random.default_rng(seed)
    y_index = {grp: i for i, grp in enumerate(groups)}
    xs, ys = {}, {}
    for _, p in df.iterrows():
        year = int(p["application_year"]) or int(df["application_year"].replace(0, np.nan).median() or 2020)
        jitter_x = rng.uniform(-0.25, 0.25)
        jitter_y = rng.uniform(-0.3, 0.3)
        xs[p["application_no"]] = year + jitter_x
        ys[p["application_no"]] = y_index.get(p["technology_group"], len(groups)) + jitter_y
    return xs, ys, y_index


def make_time_network_figure(
    df: pd.DataFrame, idea_title: str,
    similarity_threshold: float = 40.0,
    highlight_group: Optional[str] = None,
    highlight_high_risk: bool = True,
    show_patent_edges: bool = True,
) -> go.Figure:
    """시간축 네트워크맵 Plotly Figure 생성."""
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(text="표시할 데이터가 없습니다", showarrow=False)
        return fig

    groups = [g for g in TECH_GROUPS if g in set(df["technology_group"])]
    if not groups:
        groups = ["기타"]
    xs, ys, y_index = _node_positions(df, groups)

    # 아이디어 노드: 최신 연도 + 1, 대표 기술군 위치
    years = df[df["application_year"] > 0]["application_year"]
    idea_x = (int(years.max()) + 1) if len(years) else 2026
    top_group = df.groupby("technology_group").size().idxmax()
    idea_y = y_index.get(top_group, 0)

    graph = build_graph(df, idea_title, similarity_threshold)

    # ---- 엣지 그리기
    idea_edge_x, idea_edge_y = [], []
    pat_edge_x, pat_edge_y = [], []
    for u, v, attrs in graph.edges(data=True):
        if attrs["kind"] == "idea-patent":
            px, py = xs.get(v if u == "IDEA" else u), ys.get(v if u == "IDEA" else u)
            if px is None:
                continue
            idea_edge_x += [idea_x, px, None]
            idea_edge_y += [idea_y, py, None]
        elif show_patent_edges and attrs["kind"] == "patent-patent":
            if u in xs and v in xs:
                pat_edge_x += [xs[u], xs[v], None]
                pat_edge_y += [ys[u], ys[v], None]

    if pat_edge_x:
        fig.add_trace(go.Scatter(
            x=pat_edge_x, y=pat_edge_y, mode="lines",
            line=dict(width=0.5, color="rgba(150,150,150,0.35)"),
            hoverinfo="skip", name="특허 간 유사", showlegend=True))
    if idea_edge_x:
        fig.add_trace(go.Scatter(
            x=idea_edge_x, y=idea_edge_y, mode="lines",
            line=dict(width=1.2, color="rgba(214,39,40,0.45)"),
            hoverinfo="skip", name="아이디어 유사", showlegend=True))

    # ---- 특허 노드 (기술군별 trace → 범례 클릭으로 하이라이트 가능)
    for group in groups:
        sub = df[df["technology_group"] == group]
        if sub.empty:
            continue
        dimmed = highlight_group is not None and group != highlight_group
        sizes = 8 + sub["total_score"].astype(float) / 100 * 22
        border_colors = [STATUS_BORDER.get(s, "#666666") for s in sub["status"]]
        hover = [
            (f"<b>{r['title']}</b><br>출원번호: {r['application_no']}"
             f"<br>출원인: {r['applicant']} | {int(r['application_year'])}년"
             f"<br>상태: {r['status']} | 기술군: {r['technology_group']}"
             f"<br>종합 유사도: {r['total_score']:.1f}")
            for _, r in sub.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=[xs[a] for a in sub["application_no"]],
            y=[ys[a] for a in sub["application_no"]],
            mode="markers", name=group,
            marker=dict(
                size=sizes,
                color=GROUP_COLORS.get(group, "#aec7e8"),
                opacity=0.25 if dimmed else 0.9,
                line=dict(width=1.5, color=border_colors),
            ),
            text=hover, hoverinfo="text",
            customdata=sub["application_no"],
        ))

    # ---- 고위험(80점 이상) 강조 링
    if highlight_high_risk:
        risky = df[df["total_score"] >= 80]
        if len(risky):
            fig.add_trace(go.Scatter(
                x=[xs[a] for a in risky["application_no"]],
                y=[ys[a] for a in risky["application_no"]],
                mode="markers", name="고위험(80+)",
                marker=dict(size=34, symbol="circle-open",
                            color="#d62728", line=dict(width=2.5)),
                hoverinfo="skip",
            ))

    # ---- 내 아이디어 별표 노드
    fig.add_trace(go.Scatter(
        x=[idea_x], y=[idea_y], mode="markers+text",
        name="내 아이디어",
        marker=dict(size=26, symbol="star", color="#FFD700",
                    line=dict(width=2, color="#B8860B")),
        text=["★ " + (idea_title or "내 아이디어")],
        textposition="top center", hoverinfo="text",
    ))

    # ---- 공백 영역 시각화: 건수 0~1 인 (연도구간 x 기술군) 음영
    if len(years):
        y_min, y_max = int(years.min()), int(years.max())
        for grp in groups:
            grp_years = set(df[df["technology_group"] == grp]["application_year"])
            empty_span = [y for y in range(y_min, y_max + 1) if y not in grp_years]
            # 3년 이상 연속 공백이면 음영 표시
            run = []
            for y in empty_span + [None]:
                if run and (y is None or y != run[-1] + 1):
                    if len(run) >= 3:
                        fig.add_shape(
                            type="rect", x0=run[0] - 0.4, x1=run[-1] + 0.4,
                            y0=y_index[grp] - 0.42, y1=y_index[grp] + 0.42,
                            fillcolor="rgba(120,120,120,0.08)",
                            line=dict(width=0), layer="below")
                    run = []
                if y is not None:
                    run.append(y) if not run or y == run[-1] + 1 else run.clear() or run.append(y)

    fig.update_layout(
        height=620,
        xaxis=dict(title="출원연도", dtick=1, showgrid=True,
                   gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(title="기술군", tickmode="array",
                   tickvals=list(range(len(groups))), ticktext=groups,
                   showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white",
    )
    return fig
