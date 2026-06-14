# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 모니터링 수동 갱신 잡.

등록된 관심 조건(monitoring_targets)별로 검색을 실행하고, 직전 스냅샷과
비교해 신규 특허를 변경 감지(알림)로 반환한다. 스냅샷은 settings 테이블에
JSON 으로 저장하므로 별도 스키마 변경이 필요 없다. (수동 업데이트 → 변경감지)

CLI:  python -m jobs.monitor_runner
"""
import json
from datetime import datetime
from typing import List

from services.kipris_client import KiprisClient, _dedup_keys
from utils import db


def _snapshot_key(target_id) -> str:
    return f"monitor_snapshot::{target_id}"


def _build_queries(target: dict) -> List[str]:
    """관심 조건 → 검색식. 키워드 조합 + 출원인."""
    from utils.text_utils import split_keywords
    kws = split_keywords(target.get("keywords", ""))
    queries = []
    if len(kws) >= 2:
        queries.append("*".join(kws[:2]))
    if kws:
        queries.append(kws[0])
    if target.get("applicant"):
        queries.append(str(target["applicant"]))
    return list(dict.fromkeys([q for q in queries if q]))[:5] or ["프리캐스트"]


def run_target(target: dict, per_query: int = 20) -> dict:
    """관심 조건 1건 점검. 신규 특허 목록과 카운트를 반환."""
    client = KiprisClient()
    queries = _build_queries(target)
    try:
        patents = client.search_multi(queries, per_query=per_query)
    except Exception:
        patents = []

    # 현재 결과의 식별키 집합
    current_keys = set()
    key_to_patent = {}
    for p in patents:
        keys = _dedup_keys(p)
        current_keys |= keys
        for k in keys:
            key_to_patent.setdefault(k, p)

    # 직전 스냅샷 로드
    raw = db.get_setting(_snapshot_key(target.get("id")))
    prev_keys = set(json.loads(raw)) if raw else set()

    new_keys = current_keys - prev_keys
    # 신규 특허(키 중복 제거)
    new_patents, seen = [], set()
    for k in new_keys:
        p = key_to_patent.get(k)
        if not p:
            continue
        pid = id(p)
        if pid in seen:
            continue
        seen.add(pid)
        new_patents.append(p)

    # 스냅샷 갱신 + last_run_at
    db.set_setting(_snapshot_key(target.get("id")),
                   json.dumps(sorted(current_keys), ensure_ascii=False))
    if target.get("id"):
        db.touch_monitoring_target(target["id"])

    return {
        "target": target.get("name") or target.get("keywords"),
        "total": len(patents),
        "new_count": len(new_patents),
        "new_patents": new_patents,
        "first_run": not prev_keys,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def run_all(per_query: int = 20) -> List[dict]:
    """등록된 모든 관심 조건 점검."""
    return [run_target(t, per_query=per_query)
            for t in db.list_monitoring_targets()]


if __name__ == "__main__":
    db.init_db()
    for r in run_all():
        flag = "(최초 등록)" if r["first_run"] else f"신규 {r['new_count']}건"
        print(f"- {r['target']}: 총 {r['total']}건 {flag}")
