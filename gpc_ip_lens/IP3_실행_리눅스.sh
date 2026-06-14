#!/bin/bash
# IP3 (IP Cube) - Linux 실행 런처
cd "$(dirname "$0")" || exit 1
PY="python3"
command -v "$PY" >/dev/null 2>&1 || PY="python"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[오류] Python 3.11+ 가 필요합니다. 설치 후 다시 실행하세요."
    exit 1
fi
if ! "$PY" -c "import streamlit" >/dev/null 2>&1; then
    echo "최초 실행: 필요한 구성요소 설치 중... (몇 분 소요)"
    "$PY" -m pip install --disable-pip-version-check -r requirements.txt || exit 1
fi
echo "브라우저가 열립니다. 종료하려면 Ctrl+C 또는 이 창을 닫으세요."
"$PY" -m streamlit run app.py
