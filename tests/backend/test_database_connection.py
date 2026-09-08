from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import engine_from_config, event, text
from sqlalchemy.engine import make_url

from backend.app.database.connection import create_engine_and_session
from scripts.upgrade_schema import _alembic_config


def test_alembic_config_uses_psycopg_for_plain_postgresql_and_preserves_percent_encoding():
    # Deliberately pass the raw URL straight to the migration entry point.
    config = _alembic_config(
        "postgresql://demo%25user:p%40ss%25word@localhost/test?application_name=task%207"
    )
    configured_url = make_url(config.get_main_option("sqlalchemy.url"))
    assert configured_url.get_dialect().driver == "psycopg"
    engine = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.")
    try:
        assert engine.dialect.driver == "psycopg"
        assert engine.url.username == "demo%user"
        assert engine.url.password == "p@ss%word"
        assert engine.url.query["application_name"] == "task 7"
    finally:
        engine.dispose()


@pytest.mark.parametrize("scheme", ["postgresql", "postgresql+psycopg"])
def test_postgresql_urls_use_psycopg3_without_sqlite_connect_options(scheme):
    engine, factory = create_engine_and_session(f"{scheme}://demo:demo@localhost/test")
    try:
        assert engine.dialect.driver == "psycopg"
        options = {}

        class ConnectionBoundaryReached(Exception):
            pass

        def capture_connect_args(dialect, record, args, kwargs):
            options.update(kwargs)
            raise ConnectionBoundaryReached

        event.listen(engine, "do_connect", capture_connect_args)
        with pytest.raises(ConnectionBoundaryReached):
            engine.connect()
        assert options["dbname"] == "test"
        assert "check_same_thread" not in options
        assert factory.kw["bind"] is engine
    finally:
        engine.dispose()


def test_sqlite_connections_allow_cross_thread_access_and_enforce_foreign_keys():
    engine, factory = create_engine_and_session("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(connection.scalar, text("PRAGMA foreign_keys")).result() == 1
        with factory() as session:
            assert session.expire_on_commit is False
    finally:
        engine.dispose()
