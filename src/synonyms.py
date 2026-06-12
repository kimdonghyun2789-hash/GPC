"""사내 기술용어 동의어 사전.

data/synonyms.csv 를 기준으로 검색어 확장과 유사도 비교에 사용한다.
- 컬럼: 대표어, 동의어(여러 개는 | 로 구분)
- 파일이 없으면 기본 사전을 만들어 두며, Excel로 직접 수정할 수 있다.
"""
import pandas as pd

from src import config

SYNONYMS_FILE = "synonyms.csv"

# 기본 사전 (PC/건설 분야). 첫 항목이 대표어.
_DEFAULT_GROUPS = [
    ["pc", "피씨", "프리캐스트", "프리캐스트콘크리트", "precast"],
    ["중공", "중공형", "hollow"],
    ["기둥", "칼럼", "column"],
    ["중공기둥", "중공칼럼", "hollow column"],
    ["배수", "드레인", "물빠짐", "drain", "drainage"],
    ["슬리브", "관통슬리브", "sleeve"],
    ["선매립", "사전매립", "매립", "선시공", "embedded"],
    ["시공", "시공방법", "construction"],
    ["빗물", "우수", "rainwater"],
    ["배출", "방출", "discharge"],
    ["거푸집", "몰드", "form", "formwork", "mold"],
    ["철근", "보강근", "rebar", "reinforcement"],
    ["접합", "연결", "조인트", "joint", "connection"],
    ["프리스트레스", "긴장", "prestress"],
    ["보", "거더", "girder", "beam"],
    ["슬래브", "바닥판", "slab"],
]


def _file_path():
    return config.DATA_DIR / SYNONYMS_FILE


def ensure_file() -> None:
    """사전 파일이 없으면 기본 사전으로 생성한다."""
    config.ensure_dirs()
    path = _file_path()
    if path.exists():
        return
    rows = [
        {"대표어": group[0], "동의어": " | ".join(group[1:])}
        for group in _DEFAULT_GROUPS
    ]
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def load_groups() -> list:
    """동의어 그룹 목록을 반환한다. 각 그룹의 첫 항목이 대표어."""
    ensure_file()
    try:
        df = pd.read_csv(_file_path(), dtype=str).fillna("")
    except Exception:
        return [list(g) for g in _DEFAULT_GROUPS]
    groups = []
    for _, row in df.iterrows():
        main = str(row.get("대표어", "")).strip().lower()
        if not main:
            continue
        others = [
            t.strip().lower()
            for t in str(row.get("동의어", "")).split("|")
            if t.strip()
        ]
        groups.append([main] + others)
    return groups


_cache = {"mtime": None, "maps": None}


def _build_maps():
    path = _file_path()
    mtime = path.stat().st_mtime if path.exists() else None
    if _cache["maps"] is not None and _cache["mtime"] == mtime:
        return _cache["maps"]
    canonical = {}
    expansion = {}
    for group in load_groups():
        main = group[0]
        for term in group:
            canonical[term] = main
            expansion[term] = list(group)
    _cache["mtime"] = mtime
    _cache["maps"] = (canonical, expansion)
    return _cache["maps"]


def canonicalize(token: str) -> str:
    """토큰 하나를 대표어로 정규화한다."""
    canonical, _ = _build_maps()
    return canonical.get(token, token)


def canonicalize_tokens(tokens) -> set:
    """토큰 집합을 대표어 기준으로 정규화한다 (동의어 = 같은 토큰)."""
    canonical, _ = _build_maps()
    return {canonical.get(t, t) for t in tokens}


def canonicalize_list(tokens: list) -> list:
    """토큰 목록을 빈도를 유지한 채 대표어로 정규화한다 (TF-IDF용)."""
    canonical, _ = _build_maps()
    return [canonical.get(t, t) for t in tokens]


def expand_term(term: str) -> list:
    """용어의 동의어 목록(자기 자신 포함)을 반환한다."""
    _, expansion = _build_maps()
    return expansion.get(str(term).lower(), [str(term).lower()])


def english_synonym(term: str) -> str:
    """용어의 영문 동의어가 있으면 반환한다 (해외 검색용)."""
    for candidate in expand_term(term):
        if candidate.isascii() and candidate.replace(" ", "").isalpha():
            return candidate
    return ""
