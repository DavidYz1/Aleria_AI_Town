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
