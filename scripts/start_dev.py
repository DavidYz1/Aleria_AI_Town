from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIMUM_PYTHON = (3, 11)
MINIMUM_NODE = (20, 0)
REQUIRED_PYTHON_MODULES = ("fastapi", "sqlalchemy", "uvicorn")


@dataclass(frozen=True)
class StartupPlan:
    repo_root: Path
    frontend_cwd: Path
    schema_command: tuple[str, ...]
    bootstrap_command: tuple[str, ...]
    backend_command: tuple[str, ...]
    frontend_command: tuple[str, ...]


def _command_path(path: Path) -> str:
    return path.as_posix()


def build_startup_plan(
    *,
    repo_root: Path,
    python_executable: Path,
    npm_executable: Path,
) -> StartupPlan:
    python_command = _command_path(python_executable)
    npm_command = _command_path(npm_executable)
    return StartupPlan(
        repo_root=repo_root,
        frontend_cwd=repo_root / "frontend",
        schema_command=(
            python_command,
            "-m",
            "scripts.upgrade_schema",
        ),
        bootstrap_command=(
            python_command,
            "-m",
            "scripts.ensure_demo_world",
        ),
        backend_command=(
            python_command,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ),
        frontend_command=(
            npm_command,
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            "5173",
        ),
    )


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _executable_available(name: str) -> bool:
    return shutil.which(name) is not None


def _detect_node_version() -> tuple[int, int] | None:
    node = shutil.which("node")
    if node is None:
        return None
    try:
        result = subprocess.run(
            [node, "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        major, minor, *_ = result.stdout.strip().lstrip("v").split(".")
        return int(major), int(minor)
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        return None


def collect_prerequisite_errors(
    *,
    repo_root: Path,
    python_version: tuple[int, int] | None = None,
    module_available: Callable[[str], bool] = _module_available,
    executable_available: Callable[[str], bool] = _executable_available,
    node_version: tuple[int, int] | None = None,
) -> list[str]:
    errors: list[str] = []
    resolved_python = python_version or sys.version_info[:2]
    if resolved_python < MINIMUM_PYTHON:
        errors.append(
            "Python 3.11+ is required; current version is "
            f"{resolved_python[0]}.{resolved_python[1]}."
        )

    missing_modules = [
        name for name in REQUIRED_PYTHON_MODULES if not module_available(name)
    ]
    if missing_modules:
        errors.append(
            f"Missing Python packages: {', '.join(missing_modules)}. "
            "Run: python -m pip install -r backend/requirements.txt"
        )

    node_available = executable_available("node")
    if not node_available:
        errors.append(
            "Node.js 20+ is required. Install Node.js and ensure 'node' is on PATH."
        )
    else:
        resolved_node = node_version or _detect_node_version()
        if resolved_node is None or resolved_node < MINIMUM_NODE:
            rendered = "unknown" if resolved_node is None else ".".join(
                str(part) for part in resolved_node
            )
            errors.append(
                "Node.js 20+ is required; detected version is "
                f"{rendered}."
            )

    if not executable_available("npm"):
        errors.append("npm is required. Install npm and ensure it is on PATH.")

    if not (repo_root / "frontend" / "node_modules").is_dir():
        errors.append(
            "Frontend dependencies are missing. Run: cd frontend && npm install"
        )

    return errors


def _print_ready(plan: StartupPlan) -> None:
    print("Local startup prerequisites are ready.")
    print("Backend: http://127.0.0.1:8000")
    print("Frontend: http://127.0.0.1:5173")
    print("Database startup step: upgrade schema; initialize only if empty")
    print(f"Python: {plan.schema_command[0]}")
    print(f"npm: {plan.frontend_command[0]}")


def _start_process(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {
        "cwd": cwd,
        "env": environment,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)  # type: ignore[arg-type]


def _stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except OSError:
            return


def run_startup_plan(plan: StartupPlan) -> int:
    print("Preparing the existing database without resetting Demo state...")
    subprocess.run(plan.schema_command, cwd=plan.repo_root, check=True)
    subprocess.run(plan.bootstrap_command, cwd=plan.repo_root, check=True)

    environment = os.environ.copy()
    environment.setdefault("PYTHONUNBUFFERED", "1")
    processes: list[subprocess.Popen[bytes]] = []
    try:
        processes.append(
            _start_process(
                plan.backend_command,
                cwd=plan.repo_root,
                environment=environment,
            )
        )
        processes.append(
            _start_process(
                plan.frontend_command,
                cwd=plan.frontend_cwd,
                environment=environment,
            )
        )
        print("Aleria AI Town is running. Press Ctrl+C to stop both services.")
        print("Frontend: http://127.0.0.1:5173")
        print("Backend docs: http://127.0.0.1:8000/docs")
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    return return_code
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping Aleria AI Town...")
        return 0
    finally:
        for process in reversed(processes):
            _stop_process_tree(process)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or start the Aleria AI Town Backend and Frontend.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate local dependencies without changing data or starting services",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    errors = collect_prerequisite_errors(repo_root=REPO_ROOT)
    if errors:
        print("Local startup prerequisites are not ready:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    npm = shutil.which("npm")
    if npm is None:
        print("npm is unavailable after prerequisite validation.", file=sys.stderr)
        return 1
    plan = build_startup_plan(
        repo_root=REPO_ROOT,
        python_executable=Path(sys.executable),
        npm_executable=Path(npm),
    )
    _print_ready(plan)
    if args.check:
        return 0

    try:
        return run_startup_plan(plan)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Failed to start Aleria AI Town: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
