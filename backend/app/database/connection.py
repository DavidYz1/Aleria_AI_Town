from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def create_engine_and_session(
    database_url: str,
) -> tuple[Engine, sessionmaker[Session]]:
    is_sqlite = database_url.startswith("sqlite")
    engine = create_engine(
        database_url,
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
