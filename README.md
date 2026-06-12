# GPC IP Lens

아이디어별 특허 검토 관리 도구.

기술 아이디어를 입력하고 **[검토 시작]** 을 누르면 Idea ID가 자동 생성되고,
국내/해외 특허 검색 → 유사특허 분석 → 기본 통계 → 청구항 키워드 매칭 →
차별화 포인트 정리 → 보고서 생성까지 한 번에 이어집니다.

## 메뉴

| 메뉴 | 설명 |
|---|---|
| 아이디어 검토 | 아이디어 입력 후 [검토 시작] 한 번으로 전체 검토 흐름 실행 |
| 특허 검색 | 키워드로 빠르게 국내/해외 특허 검색 |
| 아이디어 관리 | 아이디어 목록, 검토상태/검토의견 관리, 보고서 열기, 삭제 |
| 관심특허 | 저장한 관심특허 관리 및 Excel 다운로드 |
| 보고서 | Idea ID별 검토 보고서(HTML)와 결과 파일(Excel) 확인 |

## 설치 및 실행 (Windows)

1. `1_처음설치.bat` 더블클릭 — 필요한 프로그램 설치, `.env` 파일 생성
2. `.env` 파일을 메모장으로 열어 설정 정보 입력 (아래 참고)
3. `2_프로그램실행.bat` 더블클릭 — 브라우저에서 자동 실행
4. 문제가 있으면 `3_오류확인.bat` 더블클릭

## 설정 (.env)

특허 검색은 KIPRISPlus(특허정보 활용서비스) 기반입니다.
`.env.example`을 복사해 `.env`를 만들고 아래 값을 입력합니다.

```
KIPRIS_API_KEY=발급받은 인증키
KIPRIS_KR_API_URL=국내특허 검색 서비스 주소
KIPRIS_FOREIGN_API_URL=해외특허 검색 서비스 주소
KIPRIS_API_FORMAT=xml
```

설정이 비어 있으면 화면에 "특허 검색을 사용할 수 없습니다. 설정 정보를
확인하세요."가 표시되고, 상세 원인은 "상세 오류 보기"에서 확인할 수 있습니다.

## 검토 흐름

```
아이디어 입력 → [검토 시작]
 → Idea ID 자동 생성 (GPC-IP-YYYYMMDD-001)
 → 아이디어 저장 → 핵심 키워드 추출 → 검색어 후보 생성
 → 특허 검색(국내/해외/국내+해외) → 유사특허 분석 (TOP 10/20/30/50 선택)
 → 기본 통계 → 청구항 키워드 매칭 → 차별화 포인트 초안
 → 보고서 생성 (HTML + Excel)
```

## 데이터와 보고서

| 파일 | 내용 |
|---|---|
| `data/idea_database.csv` / `.xlsx` | 아이디어 DB |
| `data/collected_patents.csv` / `.xlsx` | 아이디어별 수집 유사특허 |
| `data/favorite_patents.csv` / `.xlsx` | 관심특허 |
| `reports/GPC-IP-YYYYMMDD-001_report.html` | 내부 검토 보고서 |
| `reports/GPC-IP-YYYYMMDD-001_results.xlsx` | 검토 결과 파일 |

## 폴더 구조

```
app.py                  # 메인 화면
requirements.txt
.env.example
1_처음설치.bat / 2_프로그램실행.bat / 3_오류확인.bat
assets/  data/  reports/
src/
  config.py             # 설정/경로/옵션
  keyword_analysis.py   # 핵심 키워드·검색어 후보
  patent_search.py      # 검색 범위별 검색 실행
  similarity.py         # 유사특허 분석(등급/사유)
  statistics.py         # 기본 통계
  claim_mapping.py      # 청구항 키워드 매칭
  differentiation.py    # 차별화 포인트 초안
  ideas.py              # 아이디어 DB
  favorites.py          # 관심특허
  report_generator.py   # HTML/Excel 보고서
  storage.py            # CSV+Excel 저장
  utils.py
  patent_sources/kipris_source.py
  ui/components.py  ui/styles.py
```

## 주의사항

본 도구의 결과는 기술 검토 및 선행특허 조사 지원을 위한 참고자료입니다.
실제 권리범위, 침해 여부, 신규성, 진보성 판단은 변리사 검토가 필요합니다.
