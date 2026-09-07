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

    # Auth rate limits
    auth_rate_limit_enabled: bool = True
    auth_login_ip_limit: int = 20
    auth_login_ip_window: int = 900
    auth_login_email_limit: int = 10
    auth_login_email_window: int = 900
    auth_register_ip_limit: int = 10
    auth_register_ip_window: int = 3600
    auth_forgot_email_limit: int = 3
    auth_forgot_email_window: int = 3600
    auth_forgot_ip_limit: int = 10
    auth_forgot_ip_window: int = 3600

    # Password reset
    password_reset_ttl_seconds: int = 3600

    # Email (SMTP)
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@moziketo.ir"
    smtp_use_tls: bool = True
    frontend_verify_url: str = "https://pwa.moziketo.ir/auth/verify-email"
    frontend_reset_url: str = "https://pwa.moziketo.ir/auth/reset-password"
    email_verify_ttl_seconds: int = 86400

    # OAuth
    oauth_frontend_callback_url: str = "https://pwa.moziketo.ir/auth/callback"
    oauth_api_base_url: str = "https://api.moziketo.ir/api/v1"
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    apple_client_id: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""
    oauth_apple_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
