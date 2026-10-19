"""Settings loaded from a .env file.

Dev (`make dev`): the repo-root .env. Desktop app: Electron sets EXAMFORGE_ENV_FILE and EXAMFORGE_DATA_DIR
to ~/Library/Application Support/ExamForge, and the in-app Settings page writes the provider keys there.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# In a PyInstaller bundle the source tree lives under sys._MEIPASS.
ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
ENV_FILE = Path(os.getenv("EXAMFORGE_ENV_FILE", ROOT_DIR / ".env"))
load_dotenv(ENV_FILE)

DEFAULT_EFFORT = "high"


def _data_dir() -> Path:
    path = Path(os.getenv("EXAMFORGE_DATA_DIR", "data"))
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    (path / "uploads").mkdir(exist_ok=True)
    return path


class Settings:
    data_dir: Path = _data_dir()
    upload_dir: Path = data_dir / "uploads"
    db_url: str = os.getenv("EXAMFORGE_DB_URL", f"sqlite:///{data_dir / 'examforge.db'}")
    ocr_langs: str = os.getenv("OCR_LANGS", "fra+eng")
    # Built frontend served by the backend (desktop app); unset in dev, where Vite serves it.
    static_dir: str | None = os.getenv("EXAMFORGE_STATIC_DIR")

    # Read on every access so changes from the Settings page apply without a restart.
    # Provider, model and key live in services/providers.py.
    @property
    def anthropic_effort(self) -> str:
        return os.getenv("ANTHROPIC_EFFORT") or DEFAULT_EFFORT


settings = Settings()


def update_env(values: dict[str, str]) -> None:
    """Write keys into the .env file (keeping other lines) and the current process environment."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    remaining = dict(values)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in remaining.items()]
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(out) + "\n")
    try:
        ENV_FILE.chmod(0o600)  # the file holds an API key
    except OSError:
        pass
    for k, v in values.items():
        if v:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
