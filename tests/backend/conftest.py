from pathlib import Path
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


REPO_ROOT = Path(__file__).resolve().parents[2]

# 环境变量在 pydantic-settings 里优先于 `.env`，置空它们可以让四个 provider
# 无条件回到确定性替身，即便 env_file 隔离将来被改坏。守卫见
# `test_provider_isolation.py`。
LIVE_PROVIDER_ENV_VARS = (
    "CHAT_LLM_API_KEY", "EMBEDDING_API_KEY",
    "REFLECTION_API_KEY", "PLANNING_PROVIDER_API_KEY",
)
SAFE_PROVIDER_ENV = {
    "CHAT_PROVIDER": "mock",
    "CHAT_LLM_BASE_URL": "", "CHAT_LLM_MODEL": "", "CHAT_LLM_AUTH_MODE": "bearer",
    "EMBEDDING_PROVIDER": "fake",
    "EMBEDDING_BASE_URL": "", "EMBEDDING_MODEL": "", "EMBEDDING_AUTH_MODE": "bearer",
    "REFLECTION_PROVIDER": "fake",
    "REFLECTION_BASE_URL": "", "REFLECTION_MODEL": "", "REFLECTION_AUTH_MODE": "bearer",
    "PLANNING_PROVIDER_BASE_URL": "", "PLANNING_PROVIDER_MODEL": "",
    "PLANNING_PROVIDER_AUTH_MODE": "bearer",
}

# pytest imports conftest before collecting test modules. Application modules
# can construct their default app during collection, before an autouse fixture
# runs; isolate that import path too. Never inspect the repository .env here.
from backend.app.core.config import Settings, get_settings

Settings.model_config["env_file"] = None
for name in LIVE_PROVIDER_ENV_VARS:
    os.environ[name] = ""
os.environ.update(SAFE_PROVIDER_ENV)
get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolate_repository_dotenv(monkeypatch):
    """测试进程一律看不到仓库根的 `.env`。

    这个缺口在本仓库已经出现过两次症状，都不是理论风险：
    ① 开发者填了真 key 之后，任何 `create_app()` 而不注入 provider 的用例
       都会装配真实 provider 并打真实 API —— 既花钱又不确定；
    ② `.env` 把 `COGNITION_POST_COMMIT_BUDGET_SECONDS` 从默认 5 调到 20 之后，
       三条用虚拟时钟断言 deadline 的用例直接变红 —— 它们隐含依赖默认值。

    根因是同一个：`Settings` 默认读 `.env`，测试没有任何隔离。这里把 env_file
    置空，让测试只看 `Settings` 的默认值与用例自己显式传入的参数。
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in LIVE_PROVIDER_ENV_VARS:
        monkeypatch.setenv(name, "")
    for name, value in SAFE_PROVIDER_ENV.items():
        monkeypatch.setenv(name, value)
    # `get_settings` 带 lru_cache：先前缓存的实例会绕过上面的隔离。
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'aleria-test.db').as_posix()}"


@pytest.fixture
def seed_dir() -> Path:
    return REPO_ROOT / "data"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def postgres_database_url():
    """Each opt-in test migrates its own empty schema in a disposable database.

    Only this randomly named schema is removed. An existing vector extension
    in public is reused; an extension created by migration inside our schema
    is removed together with that schema. Run these opt-in tests serially.
    """
    configured = os.getenv("TEST_POSTGRES_URL")
    if not configured:
        pytest.skip("TEST_POSTGRES_URL is not set; dedicated PostgreSQL integration database required")
    url = make_url(configured)
    assert url.get_backend_name() == "postgresql", "TEST_POSTGRES_URL must be PostgreSQL"
    url = url.set(drivername="postgresql+psycopg")
    schema = "aleria_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict({"options": f"-csearch_path={schema},public"})
    try:
        yield isolated.render_as_string(hide_password=False)
    finally:
        try:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


@pytest.fixture
def plan_session(database_url, seed_dir):
    """迁移到 head 并播种的临时 SQLite 会话。绝不触碰 backend/data/aleria.db。

    沿用 test_agent_run_repository.py 的既有做法：seed_database 内部先
    upgrade_schema 到 head，再由 DemoResetService 写入世界与 NPC。
    迁移本身不带种子数据，所以不能只跑 alembic。

    session 必须经 create_engine_and_session 取得 —— 只有它会挂上
    PRAGMA foreign_keys=ON，裸 create_engine 的 SQLite 连接不校验外键。
    """
    from backend.app.database.connection import create_engine_and_session
    from scripts.seed_world import seed_database

    seed_database(database_url, seed_dir)
    _, session_factory = create_engine_and_session(database_url)
    with session_factory() as session:
        yield session


@pytest.fixture
def seeded_ids(plan_session) -> tuple[str, str]:
    """返回 (world_id, npc_id)，两者都来自真实种子数据。

    build_golden_world() 用的 ryan / shir / grey 就是 data/npcs.json 里的
    三个 NPC，所以 agent_plans 的外键直接落在种子行上，无需补建任何
    合成 NPC。这也是 golden world 必须沿用种子 id 的原因。
    """
    from backend.app.database.models import NpcProfile, WorldState

    world = plan_session.get(WorldState, "aleria-town")
    assert world is not None, "种子世界 aleria-town 缺失，seed_database 未按预期执行"

    npc = plan_session.get(NpcProfile, "ryan")
    assert npc is not None, "种子 NPC ryan 缺失，data/npcs.json 与本 fixture 不一致"
    return world.id, npc.id
