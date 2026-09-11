from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.llm.provider import ChatProvider
from backend.app.llm.embedding_provider import EmbeddingProvider


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


def get_cognition_session(request: Request) -> Generator[Session, None, None]:
    """Own a separate lazy Session for post-commit cognition, closed per request."""
    with request.app.state.session_factory() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_chat_provider(request: Request) -> ChatProvider:
    return request.app.state.chat_provider


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    return request.app.state.embedding_provider
