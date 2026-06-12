"""GPC IP Lens 설정 모듈.

환경변수(.env)와 공통 경로, 선택 옵션을 한 곳에서 관리한다.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
ASSETS_DIR = BASE_DIR / "assets"

load_dotenv(BASE_DIR / ".env")

KIPRIS_API_KEY = os.getenv("KIPRIS_API_KEY", "").strip()
KIPRIS_KR_API_URL = os.getenv("KIPRIS_KR_API_URL", "").strip()
KIPRIS_FOREIGN_API_URL = os.getenv("KIPRIS_FOREIGN_API_URL", "").strip()
KIPRIS_API_FORMAT = os.getenv("KIPRIS_API_FORMAT", "xml").strip().lower()

APP_TITLE = "GPC IP Lens"

SEARCH_SCOPES = ["국내특허", "해외특허", "국내+해외"]
TOP_N_OPTIONS = [10, 20, 30, 50]
DEFAULT_TOP_N = 20

IDEA_PLACEHOLDER = (
    "PC 중공기둥에 배수 슬리브를 선매립하여 시공 중 유입된 빗물을 "
    "외부로 배출하는 구조"
)

IDEA_STATUSES = [
    "아이디어 등록",
    "검색 완료",
    "검토 중",
    "변리사 검토 필요",
    "출원 검토",
    "출원 완료",
    "보류",
]

SIMILARITY_GRADES = ["매우 유사", "유사", "일부 유사", "참고 수준"]

SEARCH_UNAVAILABLE_MESSAGE = "특허 검색을 사용할 수 없습니다. 설정 정보를 확인하세요."
ERROR_EXPANDER_TITLE = "상세 오류 보기"

CLAIM_MAPPING_NOTICE = (
    "청구항 키워드 매칭은 기술 검토용 보조 기능이며, "
    "실제 권리범위 판단은 변리사 검토가 필요합니다."
)

REPORT_DISCLAIMER = (
    "본 보고서는 기술 검토 및 선행특허 조사 지원을 위한 참고자료입니다. "
    "실제 권리범위, 침해 여부, 신규성, 진보성 판단은 변리사 검토가 필요합니다."
)


def ensure_dirs() -> None:
    for directory in (DATA_DIR, REPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def kr_search_configured() -> bool:
    return bool(KIPRIS_API_KEY and KIPRIS_KR_API_URL)


def foreign_search_configured() -> bool:
    return bool(KIPRIS_API_KEY and KIPRIS_FOREIGN_API_URL)
