# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - exe 실행용 런처.

동작:
1. 로컬 Streamlit 서버를 현재 프로세스에서 기동 (PyInstaller 호환 방식)
2. 서버 포트가 열리면 기본 브라우저를 자동으로 연다
3. 콘솔 창을 닫거나 Ctrl+C 를 누르면 서버도 함께 종료된다

개발 모드:  python launcher.py   (또는 streamlit run app.py)
배포 모드:  실행파일 더블클릭
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PORT = int(os.environ.get("GPC_IP_LENS_PORT", "8501"))


def base_dir() -> Path:
    """app.py 가 위치한 디렉토리.

    - 개발: launcher.py 와 같은 폴더
    - PyInstaller onefile: sys._MEIPASS (번들 임시폴더)
    - PyInstaller onedir: 실행파일 옆 _internal 또는 실행파일 폴더
    """
    if getattr(sys, "frozen", False):
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS))
        exe_dir = Path(sys.executable).resolve().parent
        candidates += [exe_dir / "_internal", exe_dir]
        for c in candidates:
            if (c / "app.py").exists():
                return c
        return exe_dir
    return Path(__file__).resolve().parent


def find_free_port(start: int) -> int:
    port = start
    while port < start + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start


def wait_and_open_browser(port: int, timeout: int = 60) -> None:
    """서버 포트가 열릴 때까지 대기 후 브라우저 오픈 (백그라운드 스레드)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                webbrowser.open(f"http://localhost:{port}")
                return
        time.sleep(0.5)


def main() -> None:
    app_dir = base_dir()
    app_path = app_dir / "app.py"
    if not app_path.exists():
        print(f"[IP3] app.py 를 찾을 수 없습니다: {app_path}")
        input("Enter 를 누르면 종료합니다...")
        sys.exit(1)

    # 모듈 import 경로 보장 (frozen 환경에서 services/analyzers 등)
    sys.path.insert(0, str(app_dir))
    os.chdir(app_dir)

    port = find_free_port(PORT)
    print("=" * 56)
    print("  IP3 (IP Cube) - Idea to Patent Intelligence Platform")
    print(f"  http://localhost:{port}  (브라우저가 자동으로 열립니다)")
    print("  종료: 이 창을 닫거나 Ctrl+C")
    print("=" * 56)

    threading.Thread(target=wait_and_open_browser, args=(port,),
                     daemon=True).start()

    # PyInstaller 환경에서는 subprocess 로 streamlit 을 띄울 수 없으므로
    # (sys.executable 이 exe 자신이 됨) streamlit CLI 를 직접 호출한다.
    from streamlit.web import cli as stcli
    sys.argv = [
        "streamlit", "run", str(app_path),
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]
    try:
        sys.exit(stcli.main())
    except KeyboardInterrupt:
        print("\n[IP3] 서버를 종료합니다.")


if __name__ == "__main__":
    main()
