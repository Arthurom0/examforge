"""Settings loaded from the repo-root .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _data_dir() -> Path:
    raw = os.getenv("EXAMFORGE_DATA_DIR", "data")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    (path / "uploads").mkdir(exist_ok=True)
    return path


class Settings:
    data_dir: Path = _data_dir()
    upload_dir: Path = data_dir / "uploads"
    db_url: str = os.getenv("EXAMFORGE_DB_URL", f"sqlite:///{data_dir / 'examforge.db'}")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    anthropic_effort: str = os.getenv("ANTHROPIC_EFFORT", "high")
    ocr_langs: str = os.getenv("OCR_LANGS", "fra+eng")

    @property
    def has_api_key(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))


settings = Settings()
