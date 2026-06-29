"""
pages/5_설정.py
설정 페이지.
- 추천 조건(최근 방문 제외/카테고리 제외/도보/추천 개수/랜덤성)
- 점수 가중치(선호도/거리/가격/혼잡도/예산)
- AI 설정(사용 여부/Provider/모델명/세부 기능 토글) 및 API Key 상태 안내
※ API Key는 코드/DB에 저장하지 않고 .env 또는 Streamlit secrets로 관리한다.
"""

import streamlit as st

from services import settings as settings_service, ai_client, db, naver_map, importer
from utils.ui import page_header

page_header("설정", "내 위치·취향·추천 조건·AI·네이버 연동을 설정하세요")

s = settings_service.get_all()

# ------------------------------------------------------------------
# 내 위치 (네이버 식당 수집·도보시간 계산의 기준)
# ------------------------------------------------------------------
st.subheader("내 위치")
st.caption("회사 주소나 지역명을 정해두면 네이버 식당 자동 수집과 도보시간 계산의 기준이 됩니다.")
base_loc = st.text_input("기준 위치 (회사 주소 또는 지역명)",
                         value=s.get("base_location", "") or "",
                         placeholder="예: 서울 강남구 테헤란로 152 / 역삼역")
loc_c1, loc_c2 = st.columns(2)
if loc_c1.button("위치 저장", type="primary"):
    settings_service.set("base_location", base_loc.strip())
    st.success("내 위치를 저장했습니다.")
if loc_c2.button("이 위치로 도보시간 자동 계산", disabled=not naver_map.is_available(),
                 help="네이버 지도 키가 있으면 좌표 보유 식당의 도보시간을 자동 갱신합니다."):
    loc = base_loc.strip() or (s.get("base_location") or "")
    if not loc:
        st.error("기준 위치를 먼저 입력/저장해주세요.")
    else:
        settings_service.set("base_location", loc)
        res = importer.recompute_walk_minutes(loc)
        (st.success if res["ok"] else st.error)(res["message"])

# 연동 상태 한눈에
_cur = settings_service.get_all()
status_bits = [
    ("네이버 식당검색", naver_map.is_search_available()),
    ("네이버 지도", naver_map.is_available()),
    (f"AI({_cur.get('ai_provider')})", ai_client.is_available(_cur)),
]
st.markdown(
    "연동 상태 · " + "   ".join(
        f"{'🟢' if ok else '⚪'} {name}" for name, ok in status_bits
    )
)

st.divider()

# ------------------------------------------------------------------
# 내 취향 (user_preferences, PRD 5.5)
# ------------------------------------------------------------------
st.subheader("내 취향")
prefs = db.get_preferences()
categories = sorted({r.get("category") for r in db.list_restaurants() if r.get("category")})
all_tags = db.all_tag_names()
with st.form("prefs_form"):
    p1, p2 = st.columns(2)
    pref_cats = p1.multiselect("선호 메뉴", categories, default=prefs.get("preferred_categories", []))
    dis_cats = p2.multiselect("비선호 메뉴", categories, default=prefs.get("disliked_categories", []))
    t1, t2 = st.columns(2)
    pref_tags = t1.multiselect("선호 태그", all_tags, default=prefs.get("preferred_tags", []))
    dis_tags = t2.multiselect("비선호 태그", all_tags, default=prefs.get("disliked_tags", []))
    prefs_saved = st.form_submit_button("내 취향 저장", type="primary")
if prefs_saved:
    db.save_preferences({
        "preferred_categories": pref_cats, "disliked_categories": dis_cats,
        "preferred_tags": pref_tags, "disliked_tags": dis_tags,
        "default_budget": prefs.get("default_budget"),
        "repeat_limit_days": prefs.get("repeat_limit_days"),
    })
    st.success("내 취향을 저장했습니다. 다음 추천부터 반영됩니다.")
    st.session_state.pop("recommendations", None)

st.divider()

# ------------------------------------------------------------------
# 팀원 관리 (고정 멤버 + 비선호 메뉴)
# ------------------------------------------------------------------
st.subheader("팀원 관리")
st.caption("팀원을 등록해두면 팀 점심에서 이름만 체크하면 되고, 비선호 메뉴는 후보에서 자동 제외됩니다.")
members = db.list_team_members()
if members:
    for m in members:
        mc1, mc2, mc3 = st.columns([0.32, 0.5, 0.18])
        mc1.markdown(f"**{m['name']}**")
        mc2.caption("비선호: " + (", ".join(m["disliked_categories"]) or "없음"))
        if mc3.button("삭제", key=f"delmem_{m['id']}", use_container_width=True):
            db.delete_team_member(m["id"])
            st.rerun()

with st.form("add_member_form", clear_on_submit=True):
    a1, a2 = st.columns([0.4, 0.6])
    new_name = a1.text_input("이름", placeholder="예: 동현")
    new_dislikes = a2.multiselect("비선호 메뉴", categories)
    if st.form_submit_button("팀원 추가", type="primary"):
        if new_name.strip():
            db.add_team_member(new_name.strip(), new_dislikes)
            st.success(f"'{new_name}' 팀원을 추가했습니다.")
            st.rerun()
        else:
            st.error("이름을 입력해주세요.")

st.divider()

# ------------------------------------------------------------------
# 추천 조건
# ------------------------------------------------------------------
st.subheader("추천 조건")
with st.form("rec_settings"):
    c1, c2, c3 = st.columns(3)
    exclude_recent = c1.number_input("최근 방문 제외 기간(일)", min_value=0, value=int(s["exclude_recent_days"]))
    exclude_cat = c2.number_input("같은 메뉴 제외 기간(일)", min_value=0, value=int(s["exclude_category_days"]))
    max_walk = c3.number_input("최대 도보 시간(분)", min_value=1, value=int(s["max_walk_minutes"]))
    c4, c5 = st.columns(2)
    top_n = c4.number_input("추천 개수", min_value=1, max_value=10, value=int(s["top_n"]))
    random_weight = c5.slider("랜덤성 강도", 0, 30, int(s["random_weight"]))

    st.markdown("**점수 가중치**")
    g1, g2, g3, g4, g5 = st.columns(5)
    w_pref = g1.number_input("선호도", min_value=0.0, value=float(s["weight_preference"]), step=0.1)
    w_dist = g2.number_input("거리", min_value=0.0, value=float(s["weight_distance"]), step=0.1)
    w_price = g3.number_input("가격", min_value=0.0, value=float(s["weight_price"]), step=0.1)
    w_crowd = g4.number_input("혼잡도", min_value=0.0, value=float(s["weight_crowd"]), step=0.1)
    w_budget = g5.number_input("예산", min_value=0.0, value=float(s["weight_budget"]), step=0.1)

    rec_saved = st.form_submit_button("추천 설정 저장", type="primary")

if rec_saved:
    settings_service.set_many({
        "exclude_recent_days": exclude_recent,
        "exclude_category_days": exclude_cat,
        "max_walk_minutes": max_walk,
        "top_n": top_n,
        "random_weight": random_weight,
        "weight_preference": w_pref,
        "weight_distance": w_dist,
        "weight_price": w_price,
        "weight_crowd": w_crowd,
        "weight_budget": w_budget,
    })
    st.success("추천 설정을 저장했습니다.")
    st.session_state.pop("recommendations", None)

st.divider()

# ------------------------------------------------------------------
# AI 설정
# ------------------------------------------------------------------
st.subheader("AI 설정")
with st.form("ai_settings"):
    ai_enabled = st.toggle("AI 사용", value=bool(s["ai_enabled"]))
    c1, c2 = st.columns(2)
    providers = ["openai", "gemini", "claude"]
    provider = c1.selectbox("AI Provider", providers,
                            index=providers.index(s["ai_provider"]) if s["ai_provider"] in providers else 0)
    model = c2.text_input("모델명", value=s["ai_model"])

    st.markdown("**AI 세부 기능**")
    d1, d2, d3 = st.columns(3)
    use_rec = d1.checkbox("추천 코멘트", value=bool(s["ai_use_for_recommendation"]))
    use_memo = d2.checkbox("메모 분석", value=bool(s["ai_use_for_memo_analysis"]))
    use_budget = d3.checkbox("예산 조언", value=bool(s["ai_use_for_budget_advice"]))

    ai_saved = st.form_submit_button("AI 설정 저장", type="primary")

if ai_saved:
    settings_service.set_many({
        "ai_enabled": ai_enabled,
        "ai_provider": provider,
        "ai_model": model,
        "ai_use_for_recommendation": use_rec,
        "ai_use_for_memo_analysis": use_memo,
        "ai_use_for_budget_advice": use_budget,
    })
    st.success("AI 설정을 저장했습니다.")
    st.rerun()

# API Key 상태 안내
st.markdown("##### API Key 상태")
new_settings = settings_service.get_all()
for p in ["openai", "gemini", "claude"]:
    has_key = bool(ai_client.get_api_key(p))
    st.write(f"- {p}: {'🟢 등록됨' if has_key else '⚪ 없음'}")

st.info(
    "API Key는 코드에 하드코딩하지 않습니다.\n\n"
    "프로젝트 루트의 `.env` 파일 또는 Streamlit secrets에 다음과 같이 설정하세요:\n"
    "```\nOPENAI_API_KEY=...\nGEMINI_API_KEY=...\nANTHROPIC_API_KEY=...\n```\n"
    "API Key가 없어도 MML의 기본 추천 기능은 정상 동작합니다."
)

st.divider()

# ------------------------------------------------------------------
# 네이버 지도 설정
# ------------------------------------------------------------------
st.subheader("네이버 지도")
from services import naver_map  # noqa: E402

if naver_map.is_available():
    st.write("- 네이버 지도 키: 🟢 등록됨 (주소 검색·지도 미리보기 사용 가능)")
else:
    st.write("- 네이버 지도 키: ⚪ 없음")
    st.caption(
        "`.env`에 `NAVER_MAP_CLIENT_ID`, `NAVER_MAP_CLIENT_SECRET`을 넣으면 "
        "주소→좌표 자동 입력과 지도 미리보기가 켜집니다. "
        "키가 없어도 '네이버 지도에서 보기' 링크와 기본 추천은 정상 동작합니다."
    )
