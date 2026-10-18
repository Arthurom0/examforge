#!/usr/bin/env python3
"""Cross-platform launcher: `python run.py` sets everything up on first run, then starts
the backend (http://127.0.0.1:8000) and the frontend (http://localhost:5173)."""
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
WIN = os.name == "nt"
VPY = VENV / ("Scripts/python.exe" if WIN else "bin/python")
NPM = "npm.cmd" if WIN else "npm"


def step(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def ensure_setup() -> None:
    if not VPY.exists():
        step("Creating Python virtual environment")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    marker = VENV / ".requirements-installed"
    req = ROOT / "backend" / "requirements.txt"
    if not marker.exists() or marker.stat().st_mtime < req.stat().st_mtime:
        step("Installing backend dependencies")
        subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", "-r", str(req)])
        marker.touch()
    if not shutil.which(NPM):
        sys.exit("Node.js (npm) is required: install it from https://nodejs.org and re-run.")
    if not (ROOT / "frontend" / "node_modules").exists():
        step("Installing frontend dependencies")
        subprocess.check_call([NPM, "install"], cwd=ROOT / "frontend")
    env_file = ROOT / ".env"
    if not env_file.exists():
        shutil.copy(ROOT / ".env.example", env_file)
        print("Created .env: add your ANTHROPIC_API_KEY to it (uploading works without it).")
    if not shutil.which("tesseract"):
        print("Note: Tesseract is not installed, so scanned PDFs cannot be OCR'd (see README).")


def main() -> None:
    ensure_setup()
    step("Starting ExamForge (Ctrl+C to stop)")
    backend = subprocess.Popen(
        [str(VPY), "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"], cwd=ROOT / "backend"
    )
    frontend = subprocess.Popen([NPM, "run", "dev"], cwd=ROOT / "frontend")
    try:
        time.sleep(3)
        webbrowser.open("http://localhost:5173")
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (frontend, backend):
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
