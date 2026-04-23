import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# .env lives in the project root (one level above this file's directory)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    # LoF proxy (issues tokens for all downstream services)
    lof_client_id: str = Field(default="", alias="LOF_CLIENT_ID")
    lof_client_secret: str = Field(default="", alias="LOF_CLIENT_SECRET")
    lof_base_url: str = Field(default="https://api.leapoffaith.com/api/service", alias="LOF_BASE_URL")

    # Abstractive Health
    ah_email: str = Field(default="", alias="AH_EMAIL")
    ah_base_url: str = Field(default="https://api.abstractive.ai", alias="AH_BASE_URL")
    ah_test_mode: bool = Field(default=True, alias="AH_TEST_MODE")

    # OpenRouter (preferred) — falls back to direct OpenAI if only OPENAI_API_KEY is set
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="anthropic/claude-3.5-haiku", alias="OPENROUTER_MODEL")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret: str = Field(default="changeme", alias="JWT_SECRET")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.jwt_secret == "changeme":
        logger.warning("JWT_SECRET is set to default 'changeme' — change this before deploying")
    return settings
