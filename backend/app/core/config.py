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
    # Deployment marker. Set ENVIRONMENT=production in prod so the startup guard
    # below can refuse to boot with the DEBUG dev-user Owner backdoor enabled.
    ENVIRONMENT: str = "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod"}

    def assert_safe_for_environment(self) -> None:
        """Fail closed: prod must never run with DEBUG on (T3-07).

        In DEBUG mode an unauthenticated request resolves to a dev-user with the
        Owner role, which is an open admin backdoor. Refuse to start prod if it
        is ever enabled.
        """
        if self.is_production and self.DEBUG:
            raise RuntimeError(
                "Refusing to start: DEBUG=true with ENVIRONMENT=production. "
                "DEBUG grants an unauthenticated Owner dev-user — never enable it in production."
            )

    # Admin: fail-closed gate for destructive seed/clear endpoints
    admin_enabled: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dclaw_chat"

    # Auth — provider-neutral (Clerk, Logto, or any RS256/JWKS IdP).
    # Prefer AUTH_*; the legacy LOGTO_* values below act as fallbacks.
    AUTH_JWKS_URL: str = ""
    AUTH_ISSUER: str = ""
    AUTH_AUDIENCE: str = ""

    # Auth (Logto) — legacy aliases kept so existing deployments keep working.
    LOGTO_ENDPOINT: str = ""
    LOGTO_AUDIENCE: str = ""
    LOGTO_ISSUER: str = ""
    LOGTO_JWKS_URL: str = ""

    @property
    def auth_jwks_url(self) -> str:
        """Resolved JWKS URL: AUTH_JWKS_URL, falling back to LOGTO_JWKS_URL."""
        return self.AUTH_JWKS_URL or self.LOGTO_JWKS_URL

    @property
    def auth_issuer(self) -> str:
        """Resolved issuer: AUTH_ISSUER, falling back to LOGTO_ISSUER."""
        return self.AUTH_ISSUER or self.LOGTO_ISSUER

    @property
    def auth_audience(self) -> str:
        """Resolved audience: AUTH_AUDIENCE, falling back to LOGTO_AUDIENCE."""
        return self.AUTH_AUDIENCE or self.LOGTO_AUDIENCE

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
