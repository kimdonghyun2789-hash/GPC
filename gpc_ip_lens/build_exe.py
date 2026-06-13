# -*- coding: utf-8 -*-
"""GPC IP Lens - PyInstaller 빌드 스크립트.

사용법:
    python build_exe.py            # 권장: onedir 빌드
    python build_exe.py --onefile  # 단일 exe (시작 느림, 경로 이슈 가능)

빌드 결과:
    dist/GPC_IP_Lens/GPC_IP_Lens.exe   (onedir)
    dist/GPC_IP_Lens.exe               (onefile)

주의:
- Streamlit 은 메타데이터/정적 리소스가 필요하므로 --collect-all 옵션이 필수다.
- onefile 은 매 실행 시 임시폴더에 압축을 풀어 시작이 느리고,
  data/db 폴더가 exe 옆에 생성되므로 onedir 방식을 권장한다.
"""
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEP = ";" if os.name == "nt" else ":"  # --add-data 구분자 (Windows 는 ;)

APP_NAME = "GPC_IP_Lens"

# 함께 번들할 소스/데이터 (launcher 가 app.py 를 찾을 수 있어야 함)
DATAS = [
    ("app.py", "."),
    ("services", "services"),
    ("analyzers", "analyzers"),
    ("exporters", "exporters"),
    ("utils", "utils"),
    ("data/sample_patents.csv", "data"),
    (".env.example", "."),
    (".streamlit/config.toml", ".streamlit"),
]

COLLECT_ALL = ["streamlit", "plotly", "altair", "pandas", "sklearn",
               "reportlab", "openpyxl", "networkx", "dotenv"]

HIDDEN_IMPORTS = [
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "google.generativeai",
    "PIL", "PIL.Image", "PIL.ImageDraw",
]


def build(onefile: bool = False) -> None:
    try:
        from PyInstaller import __main__ as pyi
    except ImportError:
        print("PyInstaller 가 설치되어 있지 않습니다: pip install pyinstaller")
        sys.exit(1)

    args = [
        str(HERE / "launcher.py"),
        "--name", APP_NAME,
        "--noconfirm", "--clean",
        "--onefile" if onefile else "--onedir",
        # 콘솔 창 유지 (서버 로그 확인 + 창 닫으면 서버 종료)
        "--console",
    ]
    for src, dst in DATAS:
        path = HERE / src
        if path.exists():
            args += ["--add-data", f"{path}{SEP}{dst}"]
    for pkg in COLLECT_ALL:
        args += ["--collect-all", pkg]
    for mod in HIDDEN_IMPORTS:
        args += ["--hidden-import", mod]
    args += ["--copy-metadata", "streamlit"]

    print("PyInstaller 실행:\n  " + " ".join(args))
    pyi.run(args)

    # onedir 빌드 시 쓰기용 data/db 폴더를 배포 폴더에 미리 생성
    if not onefile:
        dist = HERE / "dist" / APP_NAME
        if dist.exists():
            for sub in ("data/patent_cache", "data/drawings", "data/exports", "db"):
                (dist / sub).mkdir(parents=True, exist_ok=True)
            sample = HERE / "data" / "sample_patents.csv"
            if sample.exists():
                shutil.copy2(sample, dist / "data" / "sample_patents.csv")
            env_example = HERE / ".env.example"
            if env_example.exists():
                shutil.copy2(env_example, dist / ".env.example")
            cfg = HERE / ".streamlit" / "config.toml"
            if cfg.exists():
                (dist / ".streamlit").mkdir(parents=True, exist_ok=True)
                shutil.copy2(cfg, dist / ".streamlit" / "config.toml")
        print(f"\n빌드 완료: {dist / (APP_NAME + '.exe')}")
    else:
        print(f"\n빌드 완료: {HERE / 'dist' / (APP_NAME + '.exe')}")
        print("onefile 모드에서는 첫 실행 시 압축 해제로 시작이 느릴 수 있습니다.")


if __name__ == "__main__":
    build(onefile="--onefile" in sys.argv)
