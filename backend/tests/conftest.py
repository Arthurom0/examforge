import os
import sys
import tempfile
from pathlib import Path

import pytest

# Isolated data dir per test session, set before the app is imported.
_tmp = tempfile.mkdtemp(prefix="examforge-test-")
os.environ["EXAMFORGE_DATA_DIR"] = _tmp
os.environ["EXAMFORGE_DB_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["EXAMFORGE_ENV_FILE"] = f"{_tmp}/.env"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
