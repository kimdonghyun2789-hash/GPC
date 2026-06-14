#!/bin/bash
# IP3 (IP Cube) - macOS 더블클릭 실행 런처
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo "  IP3 (IP Cube) - Idea to Patent Intelligence"
echo "============================================================"
echo

# 파이썬 찾기 (python3 우선)
PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then
    PY="python"
fi
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[오류] Python 이 설치되어 있지 않습니다."
    echo "       https://www.python.org/downloads 에서 Python 3.11 이상을 설치 후 다시 실행하세요."
    read -n 1 -s -r -p "아무 키나 누르면 종료합니다..."
    exit 1
fi

# 최초 1회: 필요한 패키지 설치
if ! "$PY" -c "import streamlit" >/dev/null 2>&1; then
    echo "최초 실행입니다. 필요한 구성요소를 설치합니다... (몇 분 걸릴 수 있어요)"
    echo
    "$PY" -m pip install --disable-pip-version-check -r requirements.txt || {
        echo
        echo "[오류] 구성요소 설치 실패. 인터넷 연결을 확인하고 다시 실행하세요."
        read -n 1 -s -r -p "아무 키나 누르면 종료합니다..."
        exit 1
    }
fi

echo
echo "잠시 후 브라우저가 자동으로 열립니다. 종료하려면 이 터미널 창을 닫으세요."
echo
"$PY" -m streamlit run app.py
