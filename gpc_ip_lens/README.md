# IP³ (IP Cube)

**Intellectual Property · Idea to Patent · Intelligence Platform**

아이디어를 입력하면 **Gemini API** 와 **KIPRISPlus** 데이터를 기반으로
유사특허, 대표도면, 통계, 기술발전도, 시간축 네트워크맵, AI 1차 검토 결과를
제공하는 **GPC 내부용 건설/PC 특화 특허 탐색·분석 플랫폼**입니다.
(프로그램명: IP³, 읽는 명칭: IP Cube)

단순 특허 검색기가 아니라, 검색 결과를 건설/PC 기술 관점(접합부·전단키·
생산방법·몰드·배수·방수·품질관리·유지관리·센서·시공장비)으로 재가공하여
유사특허와 기술 흐름을 빠르게 파악할 수 있게 하는 도구입니다.

> ⚠️ AI 분석 결과는 1차 스크리닝용 참고 의견이며 **최종 법률 판단이 아닙니다.**
> 출원/실시 결정 전 변리사 검토와 추가 선행기술 조사가 필요합니다.

---

## 주요 화면 (사이드바 메뉴)

| 메뉴 | 기능 |
|---|---|
| 1. Idea Canvas | 아이디어 입력, Gemini 검색어 확장, KIPRIS 검색 실행 |
| 2. Patent Radar | 유사특허 TOP N 표 + 대표도면 갤러리 + 상세 패널 |
| 3. Patent DNA | 아이디어 vs 특허 구조 비교표 + 청구항 대비표(Claim Chart) |
| 4. Landscape | 출원 동향·기술 발전 흐름·기술 공백/전략·네트워크맵(탭 4개) |
| 5. Drawing Intelligence | 대표도면 중심 검토 (정렬/캡션 자동 생성) |
| 6. AI Patent Review | Gemini 기반 1차 검토 (공통/차이/회피설계 포인트) |
| 7. History | 지난 분석 다시 불러오기 + 관심 특허(북마크) 관리 |
| 8. Export Center | Excel / PDF 리포트(도면·차트 포함) / 이미지 |
| 9. Settings | API Key, mock 전환, 유사도 가중치 조정, DB/캐시 관리 |

---

## 설치 방법

```bash
# Python 3.11 이상 필요
cd gpc_ip_lens
pip install -r requirements.txt
```

## 실행 방법 (개발)

```bash
streamlit run app.py
# 또는 launcher 로 실행 (브라우저 자동 오픈)
python launcher.py
```

## 더블클릭으로 실행하기 (exe 없이)

Python 3.11+ 만 설치돼 있으면 아래 파일을 **더블클릭**하면 자동으로 필요한
구성요소를 설치하고 브라우저가 열립니다. (최초 1회만 설치, 인터넷 필요)

- 윈도우: `IP3_실행_윈도우.bat`
- macOS: `IP3_실행_맥.command` (처음엔 우클릭 → "열기")
- 리눅스: `IP3_실행_리눅스.sh`

## Mock Data 로 실행하기

별도 설정 없이 바로 동작합니다. 기본값이 `USE_MOCK_DATA=true` 이며,
`data/sample_patents.csv` (PC 중공기둥/더블월/전단키/배수/몰드 등 33건)
기반으로 **모든 화면이 동작**합니다.

빠른 데모: **11. Settings → "샘플 데이터 로드 (데모 실행)"** 버튼을 누르면
데모 아이디어로 전체 파이프라인이 실행됩니다.

## Gemini API 설정 방법

1. https://aistudio.google.com/apikey 에서 API Key 발급
2. 두 가지 방법 중 하나로 설정:
   - `.env.example` 을 `.env` 로 복사 후 `GEMINI_API_KEY=` 에 입력
   - 앱 실행 → **11. Settings** 화면에서 입력 후 저장 (로컬 DB에 저장됨)
3. Key 가 없어도 모든 기능은 **키워드 기반 fallback** 으로 동작합니다.
   (검색어 확장, DNA 추출, 기술발전 문장화, AI 검토, 도면 캡션)

## KIPRISPlus API 연결 방법

1. https://plus.kipris.or.kr 가입 후 API Key 발급
2. Settings(또는 .env)에서 `KIPRIS_API_KEY`, `KIPRIS_BASE_URL` 입력,
   `USE_MOCK_DATA` 체크 해제 (false)
3. `services/kipris_client.py` 의 **`RealKiprisAdapter`** 클래스에서
   `TODO(실연동)` 주석 부분에 실제 endpoint 호출과 XML 파싱을 구현하세요.
   - `search()` — 검색식 실행 (예: `getWordSearch`)
   - `get_detail()` — 서지 상세 (클릭 시 호출, 자동 캐싱)
   - `get_drawing_url()` — 대표도면 (클릭 시 호출, 자동 캐싱)
   - 호출부(app.py)는 `KiprisClient` 인터페이스만 사용하므로 어댑터만
     구현하면 화면 수정 없이 실연동됩니다.

---

## exe 빌드 방법 (Windows)

```bash
# 권장: 빌드 스크립트 사용 (onedir)
python build_exe.py

# 단일 실행파일 (시작 느림)
python build_exe.py --onefile
```

직접 PyInstaller 를 쓰는 경우:

```bash
# 권장: onedir
pyinstaller --onedir --name "GPC_IP_Lens" launcher.py ^
  --add-data "app.py;." --add-data "services;services" ^
  --add-data "analyzers;analyzers" --add-data "exporters;exporters" ^
  --add-data "utils;utils" --add-data "data/sample_patents.csv;data" ^
  --collect-all streamlit --collect-all plotly --collect-all altair ^
  --copy-metadata streamlit

# onefile (리소스 경로 이슈 가능 — 아래 주의사항 참조)
pyinstaller --onefile --name "GPC_IP_Lens" launcher.py ^
  --add-data "app.py;." ... (위와 동일 옵션)
```

빌드 후 `dist/GPC_IP_Lens/GPC_IP_Lens.exe` 를 실행하면:
1. 로컬 Streamlit 서버가 자동 기동되고
2. 기본 브라우저에서 앱이 자동으로 열리며
3. 콘솔 창을 닫으면 서버도 함께 종료됩니다.

### PyInstaller 주의사항

- **onedir 방식을 권장**합니다. Streamlit 은 정적 리소스/메타데이터 의존이
  많아 `--collect-all streamlit`, `--copy-metadata streamlit` 이 필수입니다.
- onefile 은 실행 시마다 임시폴더(`%TEMP%`)에 압축을 풀어 시작이 느리고,
  백신이 차단하는 경우가 있습니다.
- 데이터(`db/gpc_ip_lens.sqlite`, `data/` 캐시·도면·내보내기)는 **exe 옆**
  폴더에 생성됩니다 — 쓰기 권한이 있는 위치에 배포하세요.
- 빌드 머신과 같은 비트(64bit) Windows 에서 실행해야 합니다.
- 사내 배포 시 `.env` 는 포함하지 말고, Settings 화면에서 키를 입력하게
  하세요.

---

## 폴더 구조

```
gpc_ip_lens/
  app.py                  # Streamlit 메인 앱 (11개 화면)
  launcher.py             # exe 런처 (서버 기동 + 브라우저 자동 오픈)
  build_exe.py            # PyInstaller 빌드 스크립트
  requirements.txt
  .env.example            # 환경변수 예시 (.env 로 복사해서 사용)
  data/
    sample_patents.csv    # mock 특허 데이터 33건
    patent_cache/         # KIPRIS 상세/도면/캡션 JSON 캐시
    drawings/             # 도면 placeholder PNG 캐시
    exports/              # Excel/PDF/이미지 내보내기 저장 위치
  db/
    gpc_ip_lens.sqlite    # ideas/patents/search_results/drawings/settings
  services/
    gemini_service.py     # Gemini 호출 (실패 시 None → fallback)
    kipris_client.py      # KIPRIS adapter (Mock/Real 교체 구조)
  analyzers/
    keyword_expander.py   # 검색어 확장 (Gemini + fallback)
    similarity.py         # 벡터/키워드/DNA/청구항/IPC → 종합 유사도
    patent_dna.py         # 특허 DNA 추출·비교
    classifier.py         # 기술군 분류 (키워드 규칙 + IPC 보정)
    statistics.py         # 통계/히트맵/공백·생존성 분석
    technology_timeline.py# 기술발전도
    network_map.py        # 시간축 네트워크맵 (Plotly + networkx)
    ai_review.py          # AI 1차 검토 (Gemini + 규칙 fallback)
  exporters/
    excel_exporter.py     # Excel (6개 시트)
    pdf_exporter.py       # PDF 리포트 (한글 CID 폰트)
    image_exporter.py     # PNG(kaleido) / HTML fallback
  utils/
    config.py             # 설정/경로 (DB > .env 우선순위, frozen 대응)
    db.py                 # SQLite 스키마/CRUD
    text_utils.py         # 한국어 토큰화/키워드
    cache_utils.py        # 파일 JSON 캐시
```

## 관련도 산정 (종합 100점) — 모드 적응 가중

신호의 신뢰도가 모드에 따라 다르므로 가중치를 다르게 둔다.

| 항목 | Gemini 모드 | Fallback 모드 | 방법 |
|---|---|---|---|
| 벡터 의미 | 0.30 | 0.28 | Gemini 임베딩 / 실패 시 문자+단어 하이브리드 TF-IDF |
| 특허 DNA | 0.25 | 0.12 | 항목별 가중 자카드 (fallback DNA는 부정확 → 저가중) |
| 키워드 | 0.20 | 0.32 | 제목/요약/청구항 일치 + 동시출현 (가장 신뢰) |
| 대표청구항 | 0.15 | 0.20 | TF-IDF cosine |
| IPC/CPC | 0.05 | 0.08 | 기술군-IPC 매핑 |
| AI 위험도 | 0.05 | 0 | Gemini 산출 시에만 반영(순환 가중 제거), 미산출 시 재정규화 |

- 사용자가 Settings 에서 가중치를 직접 조정하면 그 값이 우선한다.
- 등급: 0~29 낮음 / 30~49 관련 있음 / 50~69 유사 / **70~100 고유사·주의**
- 절대 점수보다 **순위와 근거(일치 키워드·DNA·청구항 대비표)**를 함께 본다.

## 보안

- API Key 는 코드에 하드코딩하지 않습니다 (.env 또는 로컬 settings 테이블)
- 외부 전송은 Gemini / KIPRIS API 호출에 한정됩니다
- `.env` 와 DB 파일은 `.gitignore` 처리되어 있습니다
