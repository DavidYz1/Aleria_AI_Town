import importlib
from pathlib import Path
from types import ModuleType

import pytest


def load_launcher() -> ModuleType:
    try:
        return importlib.import_module("scripts.deploy")
    except ModuleNotFoundError:
        pytest.fail("scripts.deploy launcher is missing")


def test_deployment_plan_uses_host_env_and_compose(tmp_path: Path) -> None:
    launcher = load_launcher()
    env_file = tmp_path / ".env.production"

    plan = launcher.build_deployment_plan(
        repo_root=tmp_path,
        compose_command=("/runtime/docker", "compose"),
        env_file=env_file,
    )

    prefix = (
        "/runtime/docker",
        "compose",
        "--env-file",
        env_file.as_posix(),
    )
    assert plan.compose_version_command == (
        "/runtime/docker",
        "compose",
        "version",
    )
    assert plan.config_command == prefix + ("config", "--quiet")
    assert plan.up_command == prefix + ("up", "-d", "--build")


def test_deployment_plan_supports_the_standalone_compose_command(
    tmp_path: Path,
) -> None:
    launcher = load_launcher()
    env_file = tmp_path / ".env.production"

    plan = launcher.build_deployment_plan(
        repo_root=tmp_path,
        compose_command=("/runtime/docker-compose",),
        env_file=env_file,
    )

    assert plan.compose_version_command == (
        "/runtime/docker-compose",
        "version",
    )
    assert plan.up_command == (
        "/runtime/docker-compose",
        "--env-file",
        env_file.as_posix(),
        "up",
        "-d",
        "--build",
    )


def test_first_deploy_creates_private_mock_environment_without_overwriting(
    tmp_path: Path,
) -> None:
    launcher = load_launcher()
    example = tmp_path / ".env.production.example"
    env_file = tmp_path / ".env.production"
    example.write_text(
        "CHAT_PROVIDER=mock\nCHAT_LLM_API_KEY=\nHTTP_PORT=8080\n",
        encoding="utf-8",
    )

    assert launcher.ensure_production_env(example, env_file) is True
    assert env_file.read_text(encoding="utf-8") == example.read_text(
        encoding="utf-8"
    )
    env_file.write_text("CHAT_PROVIDER=local\n", encoding="utf-8")

    assert launcher.ensure_production_env(example, env_file) is False
    assert env_file.read_text(encoding="utf-8") == "CHAT_PROVIDER=local\n"


def test_http_port_is_read_as_data_without_loading_the_env_file(tmp_path: Path) -> None:
    launcher = load_launcher()
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "HTTP_PORT=8088\nCHAT_LLM_API_KEY=do-not-print\n",
        encoding="utf-8",
    )

    assert launcher.read_http_port(env_file) == 8088


def test_frontend_registry_is_configurable_for_reliable_remote_builds() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    compose = (repo_root / "compose.yaml").read_text(encoding="utf-8")
    dockerfile = (repo_root / "frontend" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "NPM_REGISTRY: ${NPM_REGISTRY:-https://registry.npmjs.org}" in compose
    assert "ARG NPM_REGISTRY=https://registry.npmjs.org" in dockerfile
    assert 'npm config set registry "$NPM_REGISTRY"' in dockerfile


def test_backend_image_includes_runtime_prompt_resources() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dockerfile = (repo_root / "backend" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "COPY --chown=aleria:aleria prompts /app/prompts" in dockerfile
