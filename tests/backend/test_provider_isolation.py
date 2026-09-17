"""测试套件在 collection 与执行阶段都不装配真实凭据。"""

from backend.app.core.config import get_settings
from backend.app.core.config import Settings
from backend.app.llm.embedding_provider import build_embedding_provider
from backend.app.llm.factory import build_chat_provider, build_planning_provider
from backend.app.llm.reflection_provider import build_reflection_provider


LIVE_TYPES = {
    "OpenAICompatibleChatProvider", "FallbackChatProvider",
    "OpenAICompatibleReflectionProvider", "OpenAICompatibleEmbeddingProvider",
    "OpenAICompatiblePlanningProvider",
}

COLLECTION_ENV_FILE = Settings.model_config.get("env_file")
COLLECTION_SETTINGS = get_settings()


def test_repository_dotenv_is_disabled_before_test_module_collection():
    assert COLLECTION_ENV_FILE is None


def test_keyless_provider_configuration_cannot_escape_during_collection():
    assert COLLECTION_SETTINGS.chat_provider == "mock"
    assert COLLECTION_SETTINGS.embedding_provider == "fake"
    assert COLLECTION_SETTINGS.reflection_provider == "fake"
    assert not COLLECTION_SETTINGS.planning_provider_base_url
    assert not COLLECTION_SETTINGS.planning_provider_model


def test_configured_credentials_never_reach_providers_built_inside_tests():
    """四次 factory 都实际执行，并断言它们只装配本地 Provider。"""
    settings = get_settings()

    built = {
        "chat": type(build_chat_provider(settings)).__name__,
        "reflection": type(build_reflection_provider(settings)).__name__,
        "embedding": type(build_embedding_provider(settings)).__name__,
        "planning": type(build_planning_provider(settings)).__name__,
    }
    live = {name: kind for name, kind in built.items() if kind in LIVE_TYPES}
    assert not live, f"测试进程装配出了会打真实 API 的 provider：{live}"

    for name in ("chat_llm_api_key", "reflection_api_key",
                 "planning_provider_api_key", "embedding_api_key"):
        assert not getattr(settings, name), f"{name} 不得在测试进程里带值"
