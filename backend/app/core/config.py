from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = (
        f"sqlite:///{(REPO_ROOT / 'backend/data/aleria.db').as_posix()}"
    )
    frontend_origin: str = "http://127.0.0.1:5173"
    chat_provider: str = "mock"
    chat_llm_base_url: str = ""
    chat_llm_api_key: str = ""
    chat_llm_model: str = ""
    chat_llm_auth_mode: Literal["bearer", "none"] = "bearer"
    chat_llm_output_mode: Literal["structured_json", "text"] = (
        "structured_json"
    )
    chat_llm_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    chat_history_limit: int = Field(default=10, ge=1, le=50)
    chat_prompt_version: Literal["v1", "v2"] = "v2"

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_chat_provider(self) -> "Settings":
        self.chat_provider = self.chat_provider.strip().casefold()
        self.chat_llm_base_url = self.chat_llm_base_url.strip()
        self.chat_llm_api_key = self.chat_llm_api_key.strip()
        self.chat_llm_model = self.chat_llm_model.strip()

        if self.chat_provider == "mock":
            return self

        if not self.chat_llm_base_url:
            raise ValueError("CHAT_LLM_BASE_URL is required for a non-mock provider")
        if not self.chat_llm_model:
            raise ValueError("CHAT_LLM_MODEL is required for a non-mock provider")
        if self.chat_llm_auth_mode == "bearer" and not self.chat_llm_api_key:
            raise ValueError(
                "CHAT_LLM_API_KEY is required when CHAT_LLM_AUTH_MODE is bearer"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
