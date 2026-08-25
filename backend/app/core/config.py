from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    chat_prompt_version: Literal["v1", "v2", "v3"] = "v3"

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("chat_llm_auth_mode", mode="before")
    @classmethod
    def default_empty_chat_auth_mode(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "bearer"
        return value

    @model_validator(mode="after")
    def normalize_chat_provider(self) -> "Settings":
        self.chat_provider = self.chat_provider.strip().casefold() or "mock"
        self.chat_llm_base_url = self.chat_llm_base_url.strip()
        self.chat_llm_api_key = self.chat_llm_api_key.strip()
        self.chat_llm_model = self.chat_llm_model.strip()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
