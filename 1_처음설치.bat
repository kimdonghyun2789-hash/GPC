@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GPC IP Lens - 처음 설치

echo ============================================
echo  GPC IP Lens 설치를 시작합니다.
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 Python을 먼저 설치하세요.
    echo 설치 시 "Add Python to PATH" 항목을 반드시 체크하세요.
    pause
    exit /b 1
)

if not exist venv (
    echo 가상환경을 만드는 중...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo 필요한 프로그램을 설치하는 중... (몇 분 걸릴 수 있습니다)
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

if not exist .env (
    copy .env.example .env >nul
    echo.
    echo .env 파일이 만들어졌습니다. 메모장으로 열어 설정 정보를 입력하세요.
)

echo.
echo ============================================
echo  설치가 완료되었습니다.
echo  다음에는 "2_프로그램실행.bat"을 더블클릭하세요.
echo ============================================
pause
