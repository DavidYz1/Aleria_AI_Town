from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.demo import router as demo_router
from backend.app.api.npc_chat import router as npc_chat_router
from backend.app.api.npcs import router as npcs_router
from backend.app.api.player import router as player_router
from backend.app.api.quests import router as quests_router
from backend.app.api.world import router as world_router
from backend.app.api.world_tick import router as world_tick_router
from backend.app.core.config import Settings, get_settings
from backend.app.database.connection import create_engine_and_session
from backend.app.llm.factory import build_chat_provider
from backend.app.llm.provider import ChatProvider


def create_app(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
    chat_provider: ChatProvider | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    _, session_factory = create_engine_and_session(
        database_url or resolved_settings.database_url
    )
    application = FastAPI(title="Aleria AI Town API")
    application.state.session_factory = session_factory
    application.state.settings = resolved_settings
    application.state.chat_provider = (
        chat_provider or build_chat_provider(resolved_settings)
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(world_router)
    application.include_router(world_tick_router)
    application.include_router(npcs_router)
    application.include_router(npc_chat_router)
    application.include_router(player_router)
    application.include_router(quests_router)
    application.include_router(demo_router)
    return application


app = create_app()
