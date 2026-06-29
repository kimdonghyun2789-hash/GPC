"""
pages/2_식당_DB관리.py
식당 DB 관리 페이지.
- 식당 목록 표 조회(최근방문일/방문횟수/활성여부 포함)
- 식당 추가/수정/비활성화
- 엑셀 업로드(동일 식당명 업데이트), 샘플 데이터 추가
"""

import pandas as pd
import streamlit as st

from services import db, importer
from utils import date_utils

st.title("식당 DB 관리")

tab_list, tab_add, tab_upload = st.tabs(["📋 식당 목록", "➕ 추가 / 수정", "📤 엑셀 업로드"])

# ------------------------------------------------------------------
# 식당 목록
# ------------------------------------------------------------------
with tab_list:
    restaurants = db.list_restaurants()
    if not restaurants:
        st.info("등록된 식당이 없습니다. 아래에서 샘플 데이터를 추가하거나 식당을 등록하세요.")
        if st.button("샘플 데이터 추가", type="primary"):
            n = importer.add_sample_data()
            st.success(f"샘플 식당 {n}곳을 추가했습니다.")
            st.rerun()
    else:
        last_map = db.last_visited_date_map()
        count_map = db.visit_count_map()
        rows = []
        for r in restaurants:
            rows.append({
                "ID": r["id"],
                "식당명": r["name"],
                "메뉴분류": r.get("category"),
                "대표메뉴": r.get("main_menu"),
                "도보(분)": r.get("walk_minutes"),
                "평균가격": r.get("avg_price"),
                "선호도": r.get("rating"),
                "혼잡도": r.get("crowd_level"),
                "최근방문일": last_map.get(r["id"], "-"),
                "방문횟수": count_map.get(r["id"], 0),
                "활성": "✅" if r.get("is_active") else "⛔",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("##### 활성/비활성 토글")
        names = {f"{r['name']} ({'활성' if r['is_active'] else '비활성'})": r for r in restaurants}
        sel = st.selectbox("식당 선택", list(names.keys()))
        target = names[sel]
        col_a, col_b = st.columns(2)
        if col_a.button("비활성화 (추천 제외)", use_container_width=True):
            db.set_restaurant_active(target["id"], False)
            st.rerun()
        if col_b.button("활성화", use_container_width=True):
            db.set_restaurant_active(target["id"], True)
            st.rerun()

# ------------------------------------------------------------------
# 추가 / 수정
# ------------------------------------------------------------------
with tab_add:
    restaurants = db.list_restaurants()
    options = ["[새 식당 추가]"] + [r["name"] for r in restaurants]
    pick = st.selectbox("수정할 식당 선택 (또는 새로 추가)", options)
    editing = None if pick == "[새 식당 추가]" else next(r for r in restaurants if r["name"] == pick)

    with st.form("restaurant_form"):
        name = st.text_input("식당명 *", value=editing["name"] if editing else "")
        c1, c2 = st.columns(2)
        category = c1.text_input("메뉴분류", value=editing.get("category") if editing else "")
        main_menu = c2.text_input("대표메뉴", value=editing.get("main_menu") if editing else "")
        c3, c4 = st.columns(2)
        sub_menu = c3.text_input("보조메뉴", value=editing.get("sub_menu") if editing else "")
        map_url = c4.text_input("지도URL", value=editing.get("map_url") if editing else "")
        c5, c6, c7 = st.columns(3)
        walk = c5.number_input("도보시간(분)", min_value=0, value=int(editing["walk_minutes"]) if editing else 5)
        price = c6.number_input("평균가격", min_value=0, value=int(editing["avg_price"]) if editing else 10000, step=500)
        rating = c7.number_input("선호도(0~5)", min_value=0.0, max_value=5.0,
                                 value=float(editing["rating"]) if editing else 3.0, step=0.1)
        c8, c9 = st.columns(2)
        crowd = c8.selectbox("혼잡도", ["여유", "보통", "혼잡", "매우혼잡"],
                             index=["여유", "보통", "혼잡", "매우혼잡"].index(editing["crowd_level"])
                             if editing and editing.get("crowd_level") in ["여유", "보통", "혼잡", "매우혼잡"] else 1)
        open_days = c9.text_input("영업요일", value=editing.get("open_days") if editing else "월,화,수,목,금")
        c10, c11 = st.columns(2)
        can_takeout = c10.checkbox("포장가능", value=bool(editing.get("can_takeout")) if editing else False)
        can_group = c11.checkbox("단체가능", value=bool(editing.get("can_group")) if editing else True)
        memo = st.text_area("메모", value=editing.get("memo") if editing else "")

        submitted = st.form_submit_button("저장", type="primary")

    if submitted:
        if not name.strip():
            st.error("식당명은 필수입니다.")
        else:
            db.upsert_restaurant({
                "name": name.strip(), "category": category, "main_menu": main_menu,
                "sub_menu": sub_menu, "walk_minutes": walk, "avg_price": price,
                "rating": rating, "crowd_level": crowd, "open_days": open_days,
                "can_takeout": 1 if can_takeout else 0, "can_group": 1 if can_group else 0,
                "memo": memo, "map_url": map_url,
            })
            st.success(f"'{name}' 정보를 저장했습니다.")
            st.rerun()

# ------------------------------------------------------------------
# 엑셀 업로드
# ------------------------------------------------------------------
with tab_upload:
    st.markdown(
        "필수 컬럼: **식당명, 메뉴분류, 대표메뉴, 도보시간, 평균가격**\n\n"
        "선택 컬럼: 보조메뉴, 선호도, 혼잡도, 영업요일, 포장가능, 단체가능, 메모, 지도URL\n\n"
        "동일한 식당명이 있으면 새로 추가하지 않고 기존 데이터를 업데이트합니다."
    )
    uploaded = st.file_uploader("엑셀 파일(.xlsx) 업로드", type=["xlsx"])
    if uploaded is not None:
        if st.button("업로드 반영", type="primary"):
            result = importer.import_from_excel(uploaded)
            if result["ok"]:
                st.success(result["message"])
            else:
                st.error(result["message"])

    # 양식 다운로드용 샘플 DataFrame
    st.divider()
    st.markdown("##### 엑셀 양식 예시")
    sample_df = pd.DataFrame([{
        "식당명": "김치찌개집", "메뉴분류": "한식", "대표메뉴": "김치찌개",
        "도보시간": 5, "평균가격": 9000, "선호도": 4.3, "혼잡도": "보통",
        "영업요일": "월,화,수,목,금", "포장가능": "Y", "단체가능": "Y",
        "메모": "", "지도URL": "",
    }])
    st.dataframe(sample_df, use_container_width=True, hide_index=True)
