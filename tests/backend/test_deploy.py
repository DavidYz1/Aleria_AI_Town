import importlib
import json
import re
import shlex
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from backend.app.core.config import Settings


REPO_ROOT = Path(__file__).resolve().parents[2]


def docker_instructions(relative_path):
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    return [
        line.strip().split(None, 1)
        for line in source.replace("\\\n", " ").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_compose_postgresql_storage_health_and_network_boundaries():
    compose = yaml.safe_load((REPO_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "db" in services, "Compose must provision the PostgreSQL service"
    db = services["db"]
    assert db["image"] == "pgvector/pgvector:0.8.6-pg17-bookworm"
    assert db["environment"] == {
        "POSTGRES_DB": "${POSTGRES_DB:-aleria}",
        "POSTGRES_USER": "${POSTGRES_USER:-aleria}",
        "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}",
    }
    assert db["healthcheck"]["test"] == ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
    assert db["healthcheck"]["retries"] == 12
    assert db["volumes"] == ["aleria_postgres_data:/var/lib/postgresql/data"]
    assert "aleria_postgres_data" in compose["volumes"]
    assert not db.get("ports")
    assert services["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert services["backend"]["environment"]["DATABASE_URL"] == "${DATABASE_URL:-postgresql+psycopg://${POSTGRES_USER:-aleria}:${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-aleria}}"
    assert not services["backend"].get("ports")
    assert services["web"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert services["backend"]["healthcheck"]["test"][:3] == ["CMD", "python", "-c"]
    assert "http://127.0.0.1:8000/api/health" in services["backend"]["healthcheck"]["test"][3]
    assert services["web"]["healthcheck"]["test"] == ["CMD", "wget", "--quiet", "--spider", "http://127.0.0.1/healthz"]


def test_postgresql_host_test_override_only_publishes_loopback_database_port():
    path = REPO_ROOT / "compose.postgres-test.yaml"
    assert path.exists(), "Host PostgreSQL tests require a separate loopback override"
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {
        "services": {"db": {"ports": ["127.0.0.1:${TEST_POSTGRES_PORT:-55432}:5432"]}}
    }


def test_environment_examples_keep_sqlite_local_and_postgresql_in_production():
    local = dotenv_values(REPO_ROOT / ".env.example", interpolate=False)
    production = dotenv_values(REPO_ROOT / ".env.production.example", interpolate=False)
    assert make_url(local["DATABASE_URL"]).get_backend_name() == "sqlite"
    assert production.get("POSTGRES_DB") == "aleria"
    assert production.get("POSTGRES_USER") == "aleria"
    assert production.get("POSTGRES_PASSWORD") == "change-me-demo-only"
    # Compose derives DATABASE_URL from the same database credentials.
    assert not production.get("DATABASE_URL")
    assert local["CHAT_PROVIDER"] == production["CHAT_PROVIDER"] == "mock"
    assert not local["CHAT_LLM_API_KEY"] and not production["CHAT_LLM_API_KEY"]


def test_readme_production_env_block_preserves_compose_postgresql_defaults():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    environments = [
        dotenv_values(stream=StringIO(block), interpolate=False)
        for block in re.findall(r"```env\s*\n(.*?)```", readme, flags=re.DOTALL)
    ]
    production = [env for env in environments if env.get("APP_ENV") == "production"]
    assert production, "README must include a usable production environment example"
    for env in production:
        assert not env.get("DATABASE_URL"), "Production example must not override Compose with SQLite"
        assert env["POSTGRES_DB"] == "aleria"
        assert env["POSTGRES_USER"] == "aleria"
        assert env["POSTGRES_PASSWORD"] == "<replace-with-url-safe-password>"


def test_backend_image_copies_alembic_configuration_and_runs_migrations_before_serving():
    instructions = docker_instructions("backend/Dockerfile")
    copied = {}
    for instruction, arguments in instructions:
        if instruction.upper() == "COPY":
            tokens = [token for token in shlex.split(arguments) if not token.startswith("--")]
            for source in tokens[:-1]:
                copied[tokens[-1]] = source
    assert copied.get("/app/alembic.ini") == "alembic.ini", "Migration startup needs the root Alembic configuration in the image"
    assert copied["/app/backend"] == "backend"
    assert copied["/app/prompts"] == "prompts"
    command = json.loads(next(arguments for instruction, arguments in instructions if instruction == "CMD"))
    assert command[:2] == ["sh", "-c"]
    assert [part.strip() for part in command[2].split("&&")] == [
        "python -m scripts.upgrade_schema",
        "python -m scripts.ensure_demo_world",
        "exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000",
    ]


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
    compose = yaml.safe_load((REPO_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert compose["services"]["web"]["build"]["args"]["NPM_REGISTRY"] == "${NPM_REGISTRY:-https://registry.npmjs.org}"
    instructions = docker_instructions("frontend/Dockerfile")
    args = dict(arguments.split("=", 1) for instruction, arguments in instructions if instruction == "ARG")
    assert args["NPM_REGISTRY"] == "https://registry.npmjs.org"
    commands = [
        [token for token in shlex.split(command.strip()) if not token.startswith("--mount=")]
        for instruction, arguments in instructions if instruction == "RUN"
        for command in arguments.split("&&")
    ]
    assert ["npm", "config", "set", "registry", "$NPM_REGISTRY"] in commands


def test_backend_image_includes_runtime_prompt_resources() -> None:
    copies = [
        shlex.split(arguments)
        for instruction, arguments in docker_instructions("backend/Dockerfile")
        if instruction == "COPY"
    ]
    assert ["--chown=aleria:aleria", "prompts", "/app/prompts"] in copies


def compose_backend_environment() -> dict[str, str]:
    compose = yaml.safe_load((REPO_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    return compose["services"]["backend"]["environment"]


def test_compose_passes_every_backend_setting_through_to_the_container():
    """Compose 的 `environment:` 没列出的变量不会进容器。

    `--env-file` 只为 Compose 文件自身的插值提供变量，不会注入容器；而
    `.dockerignore` 排除了 `.env*`，镜像里没有 env 文件，所以 pydantic-settings
    只能读进程环境。漏列一个字段 = 该配置在 Docker 部署里**永远**取默认值。

    后果不是启动报错，而是静默降级：Embedding / Reflection 的默认值是 `fake`，
    Planning 未配置时走确定性替身。线上 Demo 会安静地展示替身行为。

    断言由 `Settings` 的字段集推导，新增字段时自动失败——本文件此前只断言
    `DATABASE_URL` 的取值，28 个认知配置因此漂移了整整一个 Stage。
    """
    environment = compose_backend_environment()
    expected = {name.upper() for name in Settings.model_fields}

    assert len(expected) >= 40, "非空前提：Settings 字段集为空会让下面的断言恒真"
    assert set(environment) == expected, (
        "compose.yaml 的 backend `environment:` 必须与 Settings 字段一一对应。"
        f" 缺失：{sorted(expected - set(environment))};"
        f" 多余：{sorted(set(environment) - expected)}"
    )


def test_compose_backend_environment_reads_each_setting_from_its_own_variable():
    """每一项都必须从**同名** Compose 变量取值。

    写成 `EMBEDDING_MODEL: ${CHAT_LLM_MODEL:-}` 这类错配不会被上一条断言发现，
    但会让部署者在 `.env.production` 里改了值却看不到任何效果。
    """
    environment = compose_backend_environment()

    assert environment, "非空前提：environment 为空会让下面的循环恒真"
    mismatched = sorted(
        key for key, value in environment.items()
        if f"${{{key}" not in str(value)
    )
    assert not mismatched, f"这些键没有引用同名变量：{mismatched}"


def compose_backend_defaults() -> dict[str, str]:
    """解析 `${KEY:-默认}` 里的默认值；没有默认值的形式不参与比对。"""
    defaults = {}
    for key, value in compose_backend_environment().items():
        match = re.fullmatch(r"\$\{" + re.escape(key) + r":-(.*)\}", str(value))
        if match:
            defaults[key] = match.group(1)
    return defaults


def test_compose_defaults_match_the_production_environment_example():
    """Compose 默认值与 `.env.production.example` 不得漂移。

    补全透传之后，同一个默认值同时写在 `compose.yaml` 与
    `.env.production.example` 里。两处不一致时症状极隐蔽：部署者删掉
    env 文件里的一行，容器就换成另一个值，且不报错。

    `DATABASE_URL` 不参与：Compose 由 POSTGRES_* 拼它，
    生产模板刻意不提供该键（见上面的 production example 断言）。
    """
    defaults = compose_backend_defaults()
    example = dotenv_values(REPO_ROOT / ".env.production.example", interpolate=False)
    shared = sorted(set(defaults) & set(example))

    assert len(shared) >= 35, f"非空前提：只比对到 {len(shared)} 个共有键，覆盖不足"
    mismatched = {
        key: (defaults[key], example[key])
        for key in shared
        if defaults[key] != (example[key] or "")
    }
    assert not mismatched, f"compose 默认值与生产模板不一致 (compose, example)：{mismatched}"


def test_production_example_keeps_the_measured_planning_timeout():
    """`.env.production.example` 的规划超时必须等于 `Settings` 默认值。

    30 秒是实测定的（见 `config.py` 的注释：20 秒会切掉本来会成功的调用，
    兜底率 53.3% → 6.7%）。`.env.example` 已有同源守卫，但部署路径此前
    根本没有这个键，因此那条守卫覆盖不到生产模板。
    """
    example = dotenv_values(REPO_ROOT / ".env.production.example", interpolate=False)
    declared = example["PLANNING_PROVIDER_TIMEOUT_SECONDS"]
    default = Settings.model_fields["planning_provider_timeout_seconds"].default

    assert float(declared) == float(default), (
        f".env.production.example 写的是 {declared}，Settings 默认值是 {default}"
    )
