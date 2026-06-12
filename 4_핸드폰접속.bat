@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GPC IP Lens - 핸드폰 접속 모드

if not exist venv (
    echo 먼저 "1_처음설치.bat"을 실행하세요.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo ============================================
echo  GPC IP Lens 핸드폰 접속 모드
echo ============================================
echo.
echo  1. 핸드폰을 이 컴퓨터와 같은 와이파이에 연결하세요.
echo  2. 프로그램이 켜지면 왼쪽 메뉴 아래 "핸드폰에서 보기"의
echo     QR코드를 핸드폰 카메라로 찍으면 바로 열립니다.
echo     (아래에 표시되는 Network URL 주소를 직접 입력해도 됩니다)
echo  3. Windows 방화벽 허용 창이 뜨면 "허용"을 누르세요.
echo.
echo  이 검은 창을 닫으면 핸드폰에서도 접속이 끊깁니다.
echo ============================================
streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
pause
