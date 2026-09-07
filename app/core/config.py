from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "moziketo-wave"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    host: str = "0.0.0.0"
    port: int = 8000

    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    database_url: str = "postgresql+asyncpg://moziketo:moziketo@localhost:5432/moziketo"
    redis_url: str = "redis://localhost:6379/0"

    media_base_url: str = "https://dl.moziketo.ir/music"
    wp_api_base_url: str = "https://moziketo.ir/wp-json"
    admin_api_key: str = ""

    cors_origins: str = "http://localhost:3000,https://moziketo.ir"

    cache_ttl_seconds: int = 120

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
