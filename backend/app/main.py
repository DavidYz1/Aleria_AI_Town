from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.world import router as world_router
from backend.app.api.world_tick import router as world_tick_router
from backend.app.core.config import get_settings
from backend.app.database.connection import create_engine_and_session


def create_app(database_url: str | None = None) -> FastAPI:
    settings = get_settings()
    _, session_factory = create_engine_and_session(
        database_url or settings.database_url
    )
    application = FastAPI(title="Aleria AI Town API")
    application.state.session_factory = session_factory
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(world_router)
    application.include_router(world_tick_router)
    return application


app = create_app()
