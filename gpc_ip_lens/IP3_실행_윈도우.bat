@echo off
chcp 65001 >nul
cd /d "%~dp0"
title IP3 (IP Cube)

echo ============================================================
echo   IP3 (IP Cube) - Idea to Patent Intelligence
echo ============================================================
echo.

rem 파이썬 명령 찾기 (py 우선, 없으면 python)
set "PY=python"
where py >nul 2>nul && set "PY=py"

%PY% --version >nul 2>nul
if errorlevel 1 (
    echo [오류] Python 이 설치되어 있지 않습니다.
    echo        https://www.python.org/downloads 에서 Python 3.11 이상을 설치하세요.
    echo        설치 첫 화면의 "Add Python to PATH" 를 꼭 체크하세요.
    echo.
    pause
    exit /b 1
)

rem 최초 1회: 필요한 패키지 설치 (streamlit 이 없으면 설치)
%PY% -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo 최초 실행입니다. 필요한 구성요소를 설치합니다... (몇 분 걸릴 수 있어요^)
    echo.
    %PY% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [오류] 구성요소 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행하세요.
        pause
        exit /b 1
    )
)

echo.
echo 잠시 후 브라우저가 자동으로 열립니다.
echo 종료하려면 이 검은 창을 닫으세요.
echo.
%PY% -m streamlit run app.py
pause
