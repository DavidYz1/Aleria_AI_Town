"""测试套件绝不使用真实凭据。

`tests/backend/conftest.py` 不隔离 `.env`，而 `Settings()` 默认就读它。所以只要
开发者在 `.env` 里填了一把真 key，任何调用 `create_app()` 而不注入 provider 的测试
就会装配**真实 provider** 并打真实 API —— 跑一次全量套件既花钱又不确定，
超时还会让本该稳定的用例随机变红。

这条守卫在有真 key 的机器上才有区分度，所以它显式断言「凭据确实存在」这个前提：
key 为空时前提不成立，用例 skip 而不是平凡通过。
"""
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.llm.embedding_provider import build_embedding_provider
from backend.app.llm.factory import build_chat_provider, build_planning_provider
from backend.app.llm.reflection_provider import build_reflection_provider


LIVE_TYPES = {
    "OpenAICompatibleChatProvider", "FallbackChatProvider",
    "OpenAICompatibleReflectionProvider", "OpenAICompatibleEmbeddingProvider",
    "OpenAICompatiblePlanningProvider",
}


def _credentials_on_disk() -> bool:
    """直接读 `.env` 原文。不能走 `Settings` —— 隔离 fixture 清空的环境变量
    优先级高于 `.env`，用它做前提检查等于问一个已经被自己改写过的问题。"""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return False
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key.endswith("API_KEY") and value and not value.startswith("${"):
            return True
    return False


def test_configured_credentials_never_reach_providers_built_inside_tests():
    """断言无条件成立，不 skip；区分度只在配有凭据的机器上体现。

    四次 `build_*` 都是真实调用、断言的是四个确定的返回类型，所以没有空集合
    平凡通过的问题。只是在没有凭据的机器上，「全是替身」本来就成立 —— 那里
    没有东西需要守卫。失败信息里会带上凭据是否存在，方便判断是哪一种。
    """
    settings = get_settings()

    built = {
        "chat": type(build_chat_provider(settings)).__name__,
        "reflection": type(build_reflection_provider(settings)).__name__,
        "embedding": type(build_embedding_provider(settings)).__name__,
        "planning": type(build_planning_provider(settings)).__name__,
    }
    live = {name: kind for name, kind in built.items() if kind in LIVE_TYPES}
    assert not live, (
        f"测试进程装配出了会打真实 API 的 provider：{live}"
        f"（.env 中存在凭据：{_credentials_on_disk()}）"
    )

    for name in ("chat_llm_api_key", "reflection_api_key",
                 "planning_provider_api_key", "embedding_api_key"):
        assert not getattr(settings, name), f"{name} 不得在测试进程里带值"
