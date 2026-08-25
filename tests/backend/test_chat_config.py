import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_mock_settings_require_no_llm_connection_details():
    settings = Settings(_env_file=None)

    assert settings.chat_provider == "mock"
    assert settings.chat_llm_base_url == ""
    assert settings.chat_llm_api_key == ""
    assert settings.chat_llm_model == ""
    assert settings.chat_llm_auth_mode == "bearer"
    assert settings.chat_llm_output_mode == "structured_json"
    assert settings.chat_llm_timeout_seconds == 10
    assert settings.chat_history_limit == 10
    assert settings.chat_prompt_version == "v3"


def test_non_mock_settings_are_stripped_and_provider_is_normalized():
    settings = Settings(
        _env_file=None,
        chat_provider="  DeepSeek  ",
        chat_llm_base_url="  https://example.test/v1/  ",
        chat_llm_api_key="  secret  ",
        chat_llm_model="  chat-model  ",
    )

    assert settings.chat_provider == "deepseek"
    assert settings.chat_llm_base_url == "https://example.test/v1/"
    assert settings.chat_llm_api_key == "secret"
    assert settings.chat_llm_model == "chat-model"


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "chat_provider": "deepseek",
            "chat_llm_base_url": "",
            "chat_llm_model": "chat-model",
            "chat_llm_api_key": "secret",
        },
        {
            "chat_provider": "deepseek",
            "chat_llm_base_url": "https://example.test/v1",
            "chat_llm_model": "",
            "chat_llm_api_key": "secret",
        },
        {
            "chat_provider": "deepseek",
            "chat_llm_base_url": "https://example.test/v1",
            "chat_llm_model": "chat-model",
            "chat_llm_api_key": "",
        },
    ],
)
def test_non_mock_settings_allow_incomplete_connection_details_for_mock_fallback(
    overrides,
):
    settings = Settings(_env_file=None, **overrides)

    assert settings.chat_provider == "deepseek"


def test_empty_auth_mode_uses_the_safe_bearer_default():
    settings = Settings(
        _env_file=None,
        chat_provider="mock",
        chat_llm_auth_mode="",
    )

    assert settings.chat_llm_auth_mode == "bearer"


def test_local_no_auth_settings_allow_an_empty_api_key():
    settings = Settings(
        _env_file=None,
        chat_provider="local",
        chat_llm_base_url="http://127.0.0.1:8001/v1",
        chat_llm_model="qwen-4b",
        chat_llm_auth_mode="none",
        chat_llm_api_key="",
    )

    assert settings.chat_provider == "local"
    assert settings.chat_llm_auth_mode == "none"
    assert settings.chat_llm_api_key == ""


@pytest.mark.parametrize("timeout", [0, -1, 121])
def test_settings_reject_invalid_timeout(timeout):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            chat_llm_timeout_seconds=timeout,
        )


@pytest.mark.parametrize("limit", [0, -1, 51])
def test_settings_reject_invalid_history_limit(limit):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chat_history_limit=limit)


def test_settings_reject_unknown_auth_mode():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chat_llm_auth_mode="query")


@pytest.mark.parametrize("mode", ["structured_json", "text"])
def test_settings_accept_supported_chat_output_modes(mode):
    settings = Settings(_env_file=None, chat_llm_output_mode=mode)

    assert settings.chat_llm_output_mode == mode


def test_settings_reject_unknown_chat_output_mode():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chat_llm_output_mode="provider_specific")


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
def test_settings_accept_supported_prompt_versions(version):
    settings = Settings(_env_file=None, chat_prompt_version=version)

    assert settings.chat_prompt_version == version


def test_settings_reject_unknown_prompt_version():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chat_prompt_version="v4")
