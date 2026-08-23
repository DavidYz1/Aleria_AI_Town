from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.llm.provider import ChatProvider


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_chat_provider(request: Request) -> ChatProvider:
    return request.app.state.chat_provider
