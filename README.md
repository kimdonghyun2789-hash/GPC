# MML (머물래)

> **make my lunch** — 오늘 점심, 1·2·3순위로 바로 결정

**MML**(머물래)은 회사 주변 식당 데이터베이스를 기반으로 오늘의 점심 식당을 **1순위·2순위·3순위**로 추천하고, 실제 방문 기록·방문 불가 사유·예산·AI 분석까지 관리하는 점심 선택 도우미 프로그램입니다.

---

## ✨ 핵심 기능

- **오늘의 점심 1·2·3순위 추천** — 하나의 묶음 안에 붙어서 표시. 1순위가 안 되면 바로 2·3순위로.
- **스마트 추천 알고리즘** — 최근 방문/같은 카테고리/도보시간/영업요일/예산/혼잡도/선호도/랜덤성을 종합. 후보가 부족하면 조건을 단계적으로 완화.
- **방문 기록** — `[여기로 방문]`으로 만족도·실제 결제금액·메모 저장. 다음 추천에 자동 반영(최근 방문 제외, 카테고리 제외, 예산 반영).
- **방문 불가** — `[방문 불가]`로 사유 선택/직접 입력 후 오늘 추천에서 즉시 제외.
- **식당 DB 관리** — 추가/수정/비활성화, 엑셀 업로드(동일 식당명 업데이트), 샘플 데이터 추가.
- **예산 관리** — 월 예산/1회 권장 예산 설정, 사용금액·남은 예산·사용률·평균 비용·진행바·초과 경고.
- **인원수 추천** — '오늘 인원'을 입력하면 단체 가능·수용 인원에 맞는 식당만 추천.
- **내 만족도 학습** — 방문 시 남긴 만족도 평균을 다음 추천 점수에 반영(피드백 루프).
- **결과 공유** — 1·2·3순위 + 네이버 링크를 복사해 팀 채팅에 바로 붙여넣기.
- **예산 페이스 예측** — 현재 지출 속도로 월말 예상 지출을 계산(키 불필요).
- **한동안 그만 보기** — 식당을 30일간 추천에서 제외(상세보기).
- **네이버 지도(선택)** — 주소→좌표 자동 입력(Geocoding), 상세보기 지도 미리보기, 길찾기 링크.
- **AI 기능(선택)** — 자연어 요청 분석, 추천 코멘트, 방문 메모 분석, 식당 요약, 예산 조언, 월별 리포트.

> ⚠️ **AI API Key가 없어도 기본 추천 기능은 정상 동작합니다.** AI는 보조 기능입니다.

---

## 🚀 실행 방법

### Windows (가장 간단)

`run.bat` 파일을 **더블클릭**하세요. 최초 1회만 가상환경(`.venv`) 생성과 패키지 설치를 자동으로 진행하고, 이후에는 바로 앱이 실행되며 브라우저가 자동으로 열립니다.

### 직접 실행 (Windows / macOS / Linux 공통)

```bash
pip install -r requirements.txt
streamlit run app.py
```

최초 실행 시 `data/mml.db`(SQLite)가 자동 생성됩니다. 식당이 없으면 화면의 **샘플 데이터 추가** 버튼으로 10개 식당을 채울 수 있습니다.

---

## 🤖 AI 설정 (선택)

API Key는 코드에 하드코딩하지 않고 `.env` 또는 Streamlit secrets로 관리합니다.

```bash
cp .env.example .env
```

```env
OPENAI_API_KEY=...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...

# 네이버 지도(NAVER Cloud Platform Maps) — 선택
NAVER_MAP_CLIENT_ID=...
NAVER_MAP_CLIENT_SECRET=...
```

`설정` 페이지에서 AI 사용 여부 / Provider(OpenAI·Gemini·Claude) / 모델명을 지정합니다. 호출 실패 시 "AI 코멘트를 불러오지 못했습니다. 기본 추천 결과를 표시합니다."를 안내하고 기본 기능은 그대로 유지됩니다.

**네이버 지도**: `NAVER_MAP_CLIENT_ID/SECRET`(NCP Maps)을 등록하면 식당 DB 관리에서 주소만으로 좌표를 자동 입력하고, 추천 상세보기에 지도 미리보기가 표시됩니다. 키가 없어도 *네이버 지도에서 보기·길찾기* 링크와 기본 추천은 정상 동작합니다.

---

## 📁 폴더 구조

```
GPC/
├─ app.py                     # 진입점: DB 초기화 + 5개 페이지 네비게이션
├─ requirements.txt
├─ README.md
├─ .env.example
├─ data/
│   ├─ mml.db                 # 최초 실행 시 자동 생성
│   └─ sample_restaurants.xlsx
├─ services/                  # 도메인 로직
│   ├─ db.py                  # SQLite 연결/테이블/CRUD/방문·불가 저장
│   ├─ recommender.py         # 1·2·3순위 추천 엔진
│   ├─ importer.py            # 엑셀 업로드 + 샘플 데이터
│   ├─ settings.py            # 설정 읽기/쓰기(+타입 캐스팅)
│   ├─ budget.py              # 월 예산 계산
│   ├─ statistics.py          # 방문 통계/리포트 데이터
│   ├─ ai_client.py           # Provider 추상화(OpenAI/Gemini/Claude)
│   ├─ ai_prompts.py          # 프롬프트 템플릿 로더
│   └─ ai_analyzer.py         # 자연어 해석/코멘트/메모분석/예산조언
├─ components/                # 재사용 UI
│   ├─ recommendation_group.py
│   ├─ restaurant_card.py
│   ├─ budget_card.py
│   ├─ sidebar.py
│   └─ metrics.py
├─ pages/                     # 멀티페이지
│   ├─ 1_오늘의_추천.py
│   ├─ 2_식당_DB관리.py
│   ├─ 3_방문기록.py
│   ├─ 4_예산관리.py
│   └─ 5_설정.py
├─ prompts/                   # AI 프롬프트(.md)
│   ├─ recommendation_comment.md
│   ├─ memo_analysis.md
│   ├─ budget_advice.md
│   └─ monthly_report.md
└─ utils/
    ├─ date_utils.py
    ├─ score_utils.py
    └─ format_utils.py
```

---

## 🗄️ 데이터베이스

SQLite(`data/mml.db`)에 다음 테이블을 자동 생성합니다.

- `restaurants` — 식당 기본 정보
- `visit_logs` — 방문 기록 (같은 날 같은 식당 중복 저장 방지)
- `unavailable_logs` — 오늘 방문 불가 식당
- `settings` — 사용자 설정값
- `budgets` — 월별 예산

---

## 🧮 추천 알고리즘 요약

```
필터:  비활성 → 블랙리스트 → 방문불가 → 휴무 → 도보초과 → 최근방문 → 카테고리중복 → 예산
점수:  선호도 + 거리 + 가격 + 혼잡도 + 예산 + 방문횟수 + 최근미방문 + 자연어요청 + 랜덤
완화:  후보 < 추천개수 → ① 카테고리 해제 ② 최근방문 완화 ③ 도보 15분 ④ 예산 제외→감점
```

기술 스택: **Python 3.11+ · Streamlit · SQLite · pandas · openpyxl · python-dotenv**
