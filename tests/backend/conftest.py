from pathlib import Path
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


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
