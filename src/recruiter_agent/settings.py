"""Application configuration loaded from environment or the local .env file."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Settings for model access and optional LangSmith tracing."""

    fireworks_api_key: SecretStr | None = None
    fireworks_model: str | None = None
    brave_search_api_key: SecretStr | None = None
    brave_search_endpoint: str = "https://api.search.brave.com/res/v1/llm/context"
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "recruiter-agent"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_agent_id: str | None = None
    langsmith_agent_environment: str | None = None

    def configure_langsmith(self) -> None:
        """Configure LangChain's process-level tracing environment."""
        if not self.langsmith_tracing:
            os.environ["LANGSMITH_TRACING"] = "false"
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
            return
        if not self.langsmith_api_key or not self.langsmith_api_key.get_secret_value():
            raise RuntimeError("Set LANGSMITH_API_KEY in .env to enable LangSmith tracing.")

        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_API_KEY"] = self.langsmith_api_key.get_secret_value()
        os.environ["LANGSMITH_PROJECT"] = self.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = self.langsmith_endpoint

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for the running process."""
    return Settings()
