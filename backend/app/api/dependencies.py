from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.llm.provider import ChatProvider
from backend.app.llm.embedding_provider import EmbeddingProvider
from backend.app.llm.reflection_provider import ReflectionProvider
from backend.app.agents.memory_retrieval import MemoryRetriever
from backend.app.agents.planner import AgentPlanner
from backend.app.agents.reflection import ReflectionEngine
from backend.app.database.cognition_repository import CognitionRepository
from backend.app.database.plan_repository import PlanRepository
from backend.app.llm.planning_provider import PlanningProvider
from backend.app.services.cognition_projection import CognitionProjectionService, EmbeddingEnrichmentService
from backend.app.world.action_rules import DEFAULT_ACTION_REGISTRY


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


def get_planning_provider(request: Request) -> PlanningProvider:
    return request.app.state.planning_provider


def get_planner(
    session: Session = Depends(get_session),
    embedding: EmbeddingProvider = Depends(get_embedding_provider),
    cognition: CognitionProjectionService = Depends(get_cognition_service),
    planning: PlanningProvider = Depends(get_planning_provider),
) -> AgentPlanner:
    """计划写入共用请求 Session，从而与 world tick 的 persist_run 同事务提交。

    检索走 cognition 的独立 Session —— MemoryRetriever 要求所在 Session 没有
    进行中的事务，与 `api/npcs.py:76` 的既有做法一致。

    Provider 由 `build_planning_provider(settings)` 在应用装配时选定，与
    chat / embedding / reflection 三者同样挂在 `app.state` 上，便于测试注入。
    """
    return AgentPlanner(
        PlanRepository(session),
        MemoryRetriever(cognition.repository, embedding),
        planning,
        DEFAULT_ACTION_REGISTRY,
    )
