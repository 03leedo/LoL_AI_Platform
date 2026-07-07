from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LoL AI Platform API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    auto_create_tables: bool = True

    database_url: str = "postgresql+asyncpg://lol:lol_dev_password@localhost:5432/lol_ai_platform"

    frontend_origin: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    riot_api_key: str = ""
    riot_platform_routing: str = "kr"
    riot_regional_routing: str = "asia"

    # Riot dev keys allow 20 req/1s and 100 req/120s app-wide; keep headroom.
    riot_rate_limit_per_second: int = 18
    riot_rate_limit_per_two_minutes: int = 95
    riot_request_max_attempts: int = 4
    riot_retry_backoff_seconds: float = 0.8

    llm_feedback_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [self.frontend_origin, *self.cors_origins.split(",")]
        return sorted({origin.strip() for origin in origins if origin.strip()})


@lru_cache
def get_settings() -> Settings:
    return Settings()
