import importlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from backend.app.database.connection import create_engine_and_session
from backend.app.database.models import WorldState
from backend.app.database.world_repository import CANONICAL_WORLD_ID


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_launcher() -> ModuleType:
    try:
        return importlib.import_module("scripts.start_dev")
    except ModuleNotFoundError:
        pytest.fail("scripts.start_dev launcher is missing")


def load_world_bootstrap() -> ModuleType:
    try:
        return importlib.import_module("scripts.ensure_demo_world")
    except ModuleNotFoundError:
        pytest.fail("scripts.ensure_demo_world bootstrap is missing")


def test_startup_plan_uses_non_destructive_schema_upgrade(tmp_path: Path) -> None:
    launcher = load_launcher()

    plan = launcher.build_startup_plan(
        repo_root=tmp_path,
        python_executable=Path("/runtime/python"),
        npm_executable=Path("/runtime/npm"),
    )

    assert plan.schema_command == (
        "/runtime/python",
        "-m",
        "scripts.upgrade_schema",
    )
    assert plan.bootstrap_command == (
        "/runtime/python",
        "-m",
        "scripts.ensure_demo_world",
    )
    assert plan.backend_command == (
        "/runtime/python",
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    )
    assert plan.frontend_command == (
        "/runtime/npm",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
    )
    assert plan.frontend_cwd == tmp_path / "frontend"
    assert "seed_world" not in " ".join(
        plan.schema_command
        + plan.bootstrap_command
        + plan.backend_command
        + plan.frontend_command
    )


def test_empty_database_is_initialized_once_without_resetting_existing_world(
    tmp_path: Path,
) -> None:
    bootstrap = load_world_bootstrap()
    database_url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"

    assert bootstrap.ensure_demo_world(database_url, REPO_ROOT / "data") is True

    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        world = session.get(WorldState, CANONICAL_WORLD_ID)
        assert world is not None
        world.tick = 17
        session.commit()

    assert bootstrap.ensure_demo_world(database_url, REPO_ROOT / "data") is False
    with session_factory() as session:
        world = session.get(WorldState, CANONICAL_WORLD_ID)
        assert world is not None
        assert world.tick == 17


def test_prerequisite_check_reports_actionable_missing_dependencies(
    tmp_path: Path,
) -> None:
    launcher = load_launcher()
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (tmp_path / "backend" / "requirements.txt").parent.mkdir()
    (tmp_path / "backend" / "requirements.txt").write_text("fastapi\n")
    (frontend / "package.json").write_text("{}")

    errors = launcher.collect_prerequisite_errors(
        repo_root=tmp_path,
        python_version=(3, 10),
        module_available=lambda _name: False,
        executable_available=lambda _name: False,
    )

    assert errors == [
        "Python 3.11+ is required; current version is 3.10.",
        "Missing Python packages: fastapi, sqlalchemy, uvicorn. "
        "Run: python -m pip install -r backend/requirements.txt",
        "Node.js 20+ is required. Install Node.js and ensure 'node' is on PATH.",
        "npm is required. Install npm and ensure it is on PATH.",
        "Frontend dependencies are missing. Run: cd frontend && npm install",
    ]


def test_check_mode_validates_real_checkout_without_starting_servers() -> None:
    launcher_script = Path(__file__).resolve().parents[2] / "scripts" / "start_dev.py"

    result = subprocess.run(
        [sys.executable, str(launcher_script), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Local startup prerequisites are ready." in result.stdout
    assert "Backend: http://127.0.0.1:8000" in result.stdout
    assert "Frontend: http://127.0.0.1:5173" in result.stdout
