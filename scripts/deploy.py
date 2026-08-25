from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DeploymentPlan:
    repo_root: Path
    env_file: Path
    compose_version_command: tuple[str, ...]
    config_command: tuple[str, ...]
    up_command: tuple[str, ...]


def _command_path(path: Path) -> str:
    return path.as_posix()


def build_deployment_plan(
    *,
    repo_root: Path,
    compose_command: Sequence[str],
    env_file: Path,
) -> DeploymentPlan:
    normalized_compose_command = tuple(compose_command)
    compose_prefix = normalized_compose_command + (
        "--env-file",
        _command_path(env_file),
    )
    return DeploymentPlan(
        repo_root=repo_root,
        env_file=env_file,
        compose_version_command=normalized_compose_command + ("version",),
        config_command=compose_prefix + ("config", "--quiet"),
        up_command=compose_prefix + ("up", "-d", "--build"),
    )


def detect_compose_command() -> tuple[str, ...] | None:
    docker = shutil.which("docker")
    if docker is not None:
        modern_command = (_command_path(Path(docker)), "compose")
        result = subprocess.run(
            modern_command + ("version",),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return modern_command

    standalone = shutil.which("docker-compose")
    if standalone is not None:
        return (_command_path(Path(standalone)),)
    return None


def ensure_production_env(example_file: Path, env_file: Path) -> bool:
    if env_file.exists():
        return False
    if not example_file.is_file():
        raise FileNotFoundError(f"Production environment example is missing: {example_file}")
    shutil.copyfile(example_file, env_file)
    if os.name != "nt":
        env_file.chmod(0o600)
    return True


def read_http_port(env_file: Path) -> int:
    port = 80
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "HTTP_PORT":
            port = int(value.strip())
            break
    if not 1 <= port <= 65535:
        raise ValueError("HTTP_PORT must be between 1 and 65535")
    return port


def wait_for_health(url: str, *, timeout_seconds: float = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(2)
    raise TimeoutError(f"Deployment health check timed out: {url}")


def run_deployment_plan(plan: DeploymentPlan, *, check_only: bool) -> None:
    subprocess.run(
        plan.compose_version_command,
        cwd=plan.repo_root,
        check=True,
    )
    subprocess.run(plan.config_command, cwd=plan.repo_root, check=True)
    if check_only:
        return

    subprocess.run(plan.up_command, cwd=plan.repo_root, check=True)
    port = read_http_port(plan.env_file)
    wait_for_health(f"http://127.0.0.1:{port}/api/health")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or deploy Aleria AI Town with Docker Compose.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate Docker Compose configuration without starting containers",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env.production",
        help="host-side production environment file",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    env_file = args.env_file
    if not env_file.is_absolute():
        env_file = (REPO_ROOT / env_file).resolve()

    try:
        created = ensure_production_env(
            REPO_ROOT / ".env.production.example",
            env_file,
        )
        if created:
            print(f"Created {env_file.name} with safe Mock AI defaults.")

        compose_command = detect_compose_command()
        if compose_command is None:
            print("Docker Compose is not available.", file=sys.stderr)
            return 1

        plan = build_deployment_plan(
            repo_root=REPO_ROOT,
            compose_command=compose_command,
            env_file=env_file,
        )
        run_deployment_plan(plan, check_only=args.check)
    except (
        FileNotFoundError,
        OSError,
        subprocess.CalledProcessError,
        TimeoutError,
        ValueError,
    ) as exc:
        print(f"Docker deployment failed: {exc}", file=sys.stderr)
        return 1

    if args.check:
        print("Docker deployment configuration is ready.")
    else:
        port = read_http_port(env_file)
        print(f"Aleria AI Town is available at http://127.0.0.1:{port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
