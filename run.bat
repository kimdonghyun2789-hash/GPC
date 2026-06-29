@echo off
REM ============================================================
REM  MML (머물래) 실행 스크립트 (Windows)
REM  - 이 파일을 더블클릭하면 됩니다.
REM  - 최초 1회: 가상환경(.venv) 생성 + 의존성 설치
REM  - 이후: 바로 앱 실행
REM ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM --- Python 설치 확인 ---
where python >nul 2>nul
if errorlevel 1 (
    echo [오류] Python을 찾을 수 없습니다.
    echo https://www.python.org 에서 Python 3.11 이상을 설치한 뒤
    echo 설치 시 "Add Python to PATH" 옵션을 체크해주세요.
    pause
    exit /b 1
)

REM --- 가상환경이 없으면 생성 ---
if not exist ".venv\Scripts\python.exe" (
    echo [설정] 가상환경을 생성합니다... (최초 1회)
    python -m venv .venv
    if errorlevel 1 (
        echo [오류] 가상환경 생성에 실패했습니다.
        pause
        exit /b 1
    )
)

REM --- 가상환경 활성화 ---
call ".venv\Scripts\activate.bat"

REM --- 의존성 설치 (설치 표식이 없을 때만) ---
if not exist ".venv\.installed" (
    echo [설정] 필요한 패키지를 설치합니다... (최초 1회, 몇 분 걸릴 수 있습니다)
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [오류] 패키지 설치에 실패했습니다.
        pause
        exit /b 1
    )
    echo done > ".venv\.installed"
)

REM --- 앱 실행 (브라우저 자동 오픈) ---
echo.
echo ============================================================
echo  MML (머물래)를 시작합니다.
echo  브라우저가 자동으로 열립니다. 종료하려면 이 창에서 Ctrl+C.
echo ============================================================
echo.
streamlit run app.py

pause
endlocal
