from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.llm.provider import ChatProvider
from backend.app.llm.embedding_provider import EmbeddingProvider
from backend.app.llm.reflection_provider import ReflectionProvider
from backend.app.agents.memory_retrieval import MemoryRetriever
from backend.app.agents.reflection import ReflectionEngine
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.services.cognition_projection import CognitionProjectionService, EmbeddingEnrichmentService


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


def get_reflection_provider(request: Request) -> ReflectionProvider:
    return request.app.state.reflection_provider


def get_cognition_service(
    session: Session = Depends(get_cognition_session),
    settings: Settings = Depends(get_app_settings),
    embedding: EmbeddingProvider = Depends(get_embedding_provider),
    reflection: ReflectionProvider = Depends(get_reflection_provider),
) -> CognitionProjectionService:
    repository = CognitionRepository(session)
    return CognitionProjectionService(repository, settings=settings,
        enrichment=EmbeddingEnrichmentService(repository, embedding),
        reflection=ReflectionEngine(repository, MemoryRetriever(repository, embedding), reflection, settings=settings))
