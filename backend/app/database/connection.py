from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker


def normalize_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def create_engine_and_session(
    database_url: str,
) -> tuple[Engine, sessionmaker[Session]]:
    url = normalize_database_url(database_url)
    is_sqlite = url.get_backend_name() == "sqlite"
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    if is_sqlite:
        event.listen(
            engine,
            "connect",
            lambda dbapi_connection, _: dbapi_connection.execute(
                "PRAGMA foreign_keys=ON"
            ),
        )
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
