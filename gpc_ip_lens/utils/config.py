# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 설정/경로 관리 모듈.

- .env 파일과 SQLite settings 테이블 양쪽에서 설정을 읽는다.
- Settings 화면에서 저장한 값(DB)이 .env 값보다 우선한다.
- PyInstaller frozen 환경에서도 경로가 올바르게 잡히도록 처리한다.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def get_base_dir() -> Path:
    """앱 루트 디렉토리를 반환한다.

    - 개발 모드: 이 파일 기준 상위 폴더 (gpc_ip_lens/)
    - PyInstaller onefile/onedir: 실행파일이 있는 폴더
      (data/, db/ 폴더를 실행파일 옆에 두어 쓰기 가능하게 한다)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "patent_cache"
DRAWINGS_DIR = DATA_DIR / "drawings"
EXPORTS_DIR = DATA_DIR / "exports"
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "gpc_ip_lens.sqlite"
SAMPLE_CSV = DATA_DIR / "sample_patents.csv"
ENV_PATH = BASE_DIR / ".env"

# PyInstaller onefile 모드에서는 번들 리소스가 sys._MEIPASS 에 풀린다.
# sample_patents.csv 같은 읽기전용 리소스는 그쪽에서 찾을 수 있어야 한다.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _bundled = Path(sys._MEIPASS) / "data" / "sample_patents.csv"
    if not SAMPLE_CSV.exists() and _bundled.exists():
        SAMPLE_CSV = _bundled


def ensure_dirs() -> None:
    """필요한 폴더가 없으면 생성한다."""
    for d in (DATA_DIR, CACHE_DIR, DRAWINGS_DIR, EXPORTS_DIR, DB_DIR):
        d.mkdir(parents=True, exist_ok=True)


ensure_dirs()
load_dotenv(ENV_PATH)


def _db_setting(key: str):
    """settings 테이블에서 값을 읽는다. (순환 import 방지를 위해 지연 import)"""
    try:
        from utils import db
        return db.get_setting(key)
    except Exception:
        return None


def get_setting(key: str, default: str = "") -> str:
    """설정값 조회. 우선순위: DB settings 테이블 > 환경변수(.env) > 기본값."""
    val = _db_setting(key)
    if val not in (None, ""):
        return val
    return os.getenv(key, default) or default


def set_setting(key: str, value: str) -> None:
    """Settings 화면에서 입력한 값을 DB settings 테이블에 저장한다."""
    from utils import db
    db.set_setting(key, value)


def get_gemini_api_key() -> str:
    return get_setting("GEMINI_API_KEY", "")


def get_kipris_api_key() -> str:
    return get_setting("KIPRIS_API_KEY", "")


def get_kipris_base_url() -> str:
    # 실제 KIPRISPlus 연동 시 예: http://plus.kipris.or.kr/openapi/rest
    return get_setting("KIPRIS_BASE_URL", "")


def use_mock_data() -> bool:
    """mock 데이터 사용 여부. KIPRIS 키가 없으면 강제로 mock 모드."""
    raw = get_setting("USE_MOCK_DATA", "true").strip().lower()
    if raw in ("false", "0", "no", "off"):
        # mock 을 끄려고 해도 키/URL 이 없으면 mock 으로 동작
        if get_kipris_api_key() and get_kipris_base_url():
            return False
    return True
