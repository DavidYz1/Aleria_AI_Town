from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'aleria-test.db').as_posix()}"


@pytest.fixture
def seed_dir() -> Path:
    return REPO_ROOT / "data"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
