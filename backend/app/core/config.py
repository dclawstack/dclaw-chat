from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "DClaw Chat"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dclaw_chat"

    # Auth (Logto)
    LOGTO_ENDPOINT: str = ""
    LOGTO_AUDIENCE: str = ""
    LOGTO_JWKS_URL: str = ""

    # AI
    OLLAMA_URL: str = "http://localhost:11434"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_URL: str = "https://openrouter.ai/api/v1"
    NVIDIA_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    WHISPER_API_URL: str = "https://api.openai.com/v1"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3002,http://localhost:1420"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
