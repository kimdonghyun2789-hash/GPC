"""
pages/2_식당_DB관리.py
식당 DB 관리 페이지.
- 식당 목록 표 조회(최근방문일/방문횟수/활성여부 포함)
- 식당 추가/수정/비활성화
- 엑셀 업로드(동일 식당명 업데이트), 샘플 데이터 추가
"""

import pandas as pd
import streamlit as st

from services import db, importer, naver_map, settings as settings_service
from utils import date_utils
from utils.ui import page_header

# 태그 추천 목록 (PRD 3.2)
TAG_SUGGESTIONS = [
    "빠른 점심", "든든함", "가성비", "비쌈", "회식 가능", "혼밥 가능",
    "해장", "깔끔", "매움", "국물", "면", "밥", "신규 방문", "자주 감", "주차 가능",
]

page_header("식당 DB 관리", "네이버 자동 수집·직접 추가·엑셀 업로드로 회사 주변 식당을 관리하세요")

tab_list, tab_naver, tab_add, tab_upload = st.tabs(
    ["📋 식당 목록", "🔎 네이버에서 가져오기", "➕ 추가 / 수정", "📤 엑셀 · 붙여넣기"]
)

# ------------------------------------------------------------------
# 네이버 지역 검색으로 회사 주변 식당 자동 수집 (PRD 3.1)
# ------------------------------------------------------------------
with tab_naver:
    st.markdown(
        "회사 주소(또는 지역명)를 입력하면 **네이버 지역 검색**으로 주변 식당을 자동으로 "
        "수집해 DB에 추가합니다. 동일 식당명은 기존 정보를 업데이트합니다."
    )
    if not naver_map.is_search_available():
        st.warning(
            "네이버 지역 검색 키가 없습니다. `.env`에 "
            "`NAVER_SEARCH_CLIENT_ID`, `NAVER_SEARCH_CLIENT_SECRET`(네이버 개발자센터 검색 API)를 "
            "등록하면 자동 수집이 활성화됩니다. 키가 없어도 직접 추가/엑셀 업로드는 가능합니다."
        )

    base_default = settings_service.get("base_location", "") or ""
    base_location = st.text_input("기준 위치 (회사 주소 또는 지역명)", value=base_default,
                                  placeholder="예: 서울 강남구 테헤란로 또는 역삼역")
    keywords = st.multiselect("검색 키워드", importer.NAVER_SEARCH_KEYWORDS,
                              default=importer.NAVER_SEARCH_KEYWORDS)
    display = st.slider("키워드당 가져올 식당 수", 1, 5, 5)

    if st.button("네이버에서 식당 가져오기", type="primary",
                 disabled=not naver_map.is_search_available()):
        if not base_location.strip():
            st.error("기준 위치를 입력해주세요.")
        else:
            settings_service.set("base_location", base_location.strip())
            with st.spinner("네이버에서 주변 식당을 수집 중..."):
                result = importer.import_from_naver(base_location.strip(), keywords, display)
            if result["ok"]:
                st.success(result["message"])
                cols = st.columns(min(5, len(result["by_keyword"]) or 1))
                for i, (kw, cnt) in enumerate(result["by_keyword"].items()):
                    cols[i % len(cols)].metric(kw, f"{cnt}곳")
            else:
                st.error(result["message"])

    st.divider()
    st.markdown("**좌표 기반 도보시간 자동 계산**")
    st.caption("기준 위치에서 각 식당(좌표 보유)까지의 직선거리로 도보시간을 추정해 갱신합니다.")
    if st.button("도보시간 자동 계산", disabled=not naver_map.is_available()):
        loc = settings_service.get("base_location", "") or base_location
        if not loc:
            st.error("기준 위치를 먼저 입력/저장해주세요.")
        else:
            res = importer.recompute_walk_minutes(loc)
            (st.success if res["ok"] else st.error)(res["message"])

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
        tmap = db.tags_map()
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
                "상태": r.get("status") or "정상",
                "태그": ", ".join(tmap.get(r["id"], [])),
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
    geo_key = f"geo_{editing['id'] if editing else 'new'}"

    # --- 네이버 지도로 주소 → 좌표 검색 (선택, 폼 밖에서 처리) ---
    with st.expander("📍 네이버 지도로 주소 검색 (좌표 자동 입력)"):
        if not naver_map.is_available():
            st.caption("네이버 지도 키(NAVER_MAP_CLIENT_ID/SECRET)를 .env에 등록하면 "
                       "주소만으로 좌표를 자동으로 채울 수 있습니다. (키 없이도 식당 등록은 가능)")
        gq = st.text_input("주소 또는 장소명", key=f"gq_{geo_key}",
                           placeholder="예: 서울 강남구 테헤란로 152")
        if st.button("좌표 검색", key=f"gbtn_{geo_key}"):
            if not naver_map.is_available():
                st.warning("네이버 지도 키가 없어 검색할 수 없습니다. 주소/좌표를 직접 입력하세요.")
            else:
                geo = naver_map.geocode(gq)
                if geo:
                    st.session_state[geo_key] = geo
                    st.success(f"좌표를 찾았습니다: {geo['address']} "
                               f"({geo['lat']:.5f}, {geo['lng']:.5f})")
                else:
                    st.warning("주소를 찾지 못했습니다. 직접 입력해주세요.")

    geo = st.session_state.get(geo_key)

    # --- AI 태그 추천 (PRD Phase 5) ---
    ai_tag_key = f"aitags_{editing['id'] if editing else 'new'}"
    if editing:
        with st.expander("🤖 AI 태그 추천"):
            from services import ai_analyzer, ai_client
            _settings = settings_service.get_all()
            if not ai_client.is_available(_settings):
                st.caption("AI를 켜고 API Key를 등록하면 메뉴/메모를 바탕으로 태그를 추천합니다.")
            elif st.button("AI로 태그 추천받기", key=f"aibtn_{ai_tag_key}"):
                memos = [v["memo"] for v in db.list_visit_logs()
                         if v["restaurant_id"] == editing["id"] and v.get("memo")]
                with st.spinner("AI가 태그를 분석 중..."):
                    sugg = ai_analyzer.suggest_tags(editing, memos, _settings)
                if sugg:
                    # 기존 태그와 합쳐 저장
                    merged = list(dict.fromkeys(db.list_tags(editing["id"]) + sugg))
                    db.set_tags(editing["id"], merged)
                    st.success("추천 태그: " + ", ".join(sugg) + " (저장됨)")
                    st.rerun()
                else:
                    st.info("태그를 추천하지 못했습니다.")

    def _pref(field, default=None):
        """세션 검색결과 > 기존 데이터 > 기본값 순으로 초기값을 고른다."""
        if geo and field in ("address", "latitude", "longitude"):
            return {"address": geo["address"], "latitude": geo["lat"],
                    "longitude": geo["lng"]}[field]
        if editing and editing.get(field) is not None:
            return editing.get(field)
        return default

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
        price = c6.number_input("평균가격(1인)", min_value=0, value=int(editing["avg_price"]) if editing else 10000, step=500)
        rating = c7.number_input("선호도(0~5)", min_value=0.0, max_value=5.0,
                                 value=float(editing["rating"]) if editing else 3.0, step=0.1)
        c8, c9 = st.columns(2)
        crowd = c8.selectbox("혼잡도", ["여유", "보통", "혼잡", "매우혼잡"],
                             index=["여유", "보통", "혼잡", "매우혼잡"].index(editing["crowd_level"])
                             if editing and editing.get("crowd_level") in ["여유", "보통", "혼잡", "매우혼잡"] else 1)
        open_days = c9.text_input("영업요일", value=editing.get("open_days") if editing else "월,화,수,목,금")
        c10, c11, c12 = st.columns(3)
        can_takeout = c10.checkbox("포장가능", value=bool(editing.get("can_takeout")) if editing else False)
        can_group = c11.checkbox("단체가능", value=bool(_pref("can_group", True)))
        max_party = c12.number_input("수용 인원(0=제한없음)", min_value=0,
                                     value=int(_pref("max_party", 0) or 0))

        address = st.text_input("주소", value=_pref("address", "") or "")
        c13, c14 = st.columns(2)
        latitude = c13.number_input("위도(latitude)", value=float(_pref("latitude", 0.0) or 0.0),
                                    format="%.6f")
        longitude = c14.number_input("경도(longitude)", value=float(_pref("longitude", 0.0) or 0.0),
                                     format="%.6f")
        # 상태 + 태그 (PRD 3.10 / 3.2)
        status_options = ["정상", "자주 만석", "휴무 확인 필요", "폐업 의심", "신규 확인 필요"]
        cur_status = (editing.get("status") if editing else "정상") or "정상"
        status = st.selectbox("상태", status_options,
                              index=status_options.index(cur_status) if cur_status in status_options else 0)
        cur_tags = db.list_tags(editing["id"]) if editing else []
        tag_suggestions = sorted(set(TAG_SUGGESTIONS) | set(db.all_tag_names()) | set(cur_tags))
        tags = st.multiselect("태그", tag_suggestions, default=cur_tags,
                              help="빠른 점심·가성비·해장·국물 등. 추천 모드/검색에 활용됩니다.")
        custom_tags = st.text_input("태그 직접 추가 (쉼표로 구분)", value="")
        memo = st.text_area("메모", value=editing.get("memo") if editing else "")

        submitted = st.form_submit_button("저장", type="primary")

    if submitted:
        if not name.strip():
            st.error("식당명은 필수입니다.")
        else:
            rid = db.upsert_restaurant({
                "name": name.strip(), "category": category, "main_menu": main_menu,
                "sub_menu": sub_menu, "walk_minutes": walk, "avg_price": price,
                "rating": rating, "crowd_level": crowd, "open_days": open_days,
                "can_takeout": 1 if can_takeout else 0, "can_group": 1 if can_group else 0,
                "max_party": int(max_party), "address": address or None,
                "latitude": latitude or None, "longitude": longitude or None,
                "status": status, "memo": memo, "map_url": map_url,
            })
            # 태그 동기화(선택 + 직접 입력)
            all_tags = list(tags) + [t.strip() for t in custom_tags.split(",") if t.strip()]
            db.set_tags(rid, all_tags)
            st.session_state.pop(geo_key, None)
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
            (st.success if result["ok"] else st.error)(result["message"])

    # 붙여넣기로 추가 (엑셀/구글시트에서 헤더 포함 복사 → 붙여넣기)
    st.divider()
    st.markdown("##### 또는 붙여넣기로 추가")
    st.caption("엑셀/구글시트에서 **헤더 행 포함**해 복사한 뒤 아래에 붙여넣으세요. (탭 또는 콤마 구분 자동 인식)")
    paste_text = st.text_area(
        "식당 표 붙여넣기", height=140,
        placeholder="식당명\t메뉴분류\t대표메뉴\t도보시간\t평균가격\n김치찌개집\t한식\t김치찌개\t5\t9000",
    )
    if st.button("붙여넣기 반영", key="paste_rest"):
        result = importer.import_from_pasted_text(paste_text)
        (st.success if result["ok"] else st.error)(result["message"])

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
