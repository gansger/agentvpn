"""Central application settings."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "production"
    public_domain: str
    telegram_bot_token: SecretStr
    telegram_webhook_secret: SecretStr
    session_secret: SecretStr
    csrf_secret: SecretStr
    admin_telegram_ids: Annotated[tuple[int, ...], NoDecode] = ()
    cors_origins: Annotated[tuple[str, ...], NoDecode] = ()

    database_url: SecretStr
    redis_url: SecretStr
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)

    session_cookie_name: str = "agentvpn_session"
    session_ttl_seconds: int = Field(default=3600, ge=300, le=86400)
    telegram_auth_max_age_seconds: int = Field(default=300, ge=30, le=3600)
    telegram_replay_ttl_seconds: int = Field(default=600, ge=60, le=86400)
    cookie_secure: bool = True
    session_cookie_samesite: Literal["lax", "strict", "none"] = "none"
    auth_rate_limit_per_minute: int = Field(default=20, ge=1, le=1000)
    enable_mock_payments: bool = False
    enable_enot_payments: bool = False

    enot_api_base_url: AnyHttpUrl = AnyHttpUrl("https://api.enot.io")
    enot_shop_id: str | None = None
    enot_secret_key: SecretStr | None = None
    enot_webhook_additional_key: SecretStr | None = None
    enot_sbp_service_code: Literal["sbp", "p2p_sbp"] = "sbp"
    enot_payment_expire_minutes: int = Field(default=30, ge=1, le=7200)

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(int(item.strip()) for item in value.split(",") if item.strip())
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
        return value

    @field_validator("public_domain")
    @classmethod
    def validate_public_domain(cls, value: str) -> str:
        domain = value.strip().rstrip("/")
        if not domain or "://" in domain or "/" in domain:
            raise ValueError("PUBLIC_DOMAIN must be a domain name without scheme or path")
        return domain

    @field_validator(
        "telegram_webhook_secret",
        "session_secret",
        "csrf_secret",
    )
    @classmethod
    def require_long_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("application secrets must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> AppSettings:
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if self.app_env == "production" and self.enable_mock_payments:
            raise ValueError("ENABLE_MOCK_PAYMENTS must be false in production")
        if self.enable_enot_payments and not all(
            (self.enot_shop_id, self.enot_secret_key, self.enot_webhook_additional_key)
        ):
            raise ValueError(
                "ENOT_SHOP_ID, ENOT_SECRET_KEY and ENOT_WEBHOOK_ADDITIONAL_KEY "
                "are required when ENABLE_ENOT_PAYMENTS=true"
            )
        if self.app_env == "production" and self.enot_api_base_url.scheme != "https":
            raise ValueError("ENOT_API_BASE_URL must use HTTPS in production")
        if self.app_env == "production" and self.enot_api_base_url.host != "api.enot.io":
            raise ValueError("ENOT_API_BASE_URL must use the official ENOT API host in production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        origins = list(self.cors_origins)
        public_origin = f"https://{self.public_domain.strip().rstrip('/')}"
        if public_origin not in origins:
            origins.append(public_origin)
        return origins

    @property
    def public_origin(self) -> str:
        return f"https://{self.public_domain}"

    @property
    def enot_webhook_url(self) -> str:
        return f"{self.public_origin}/api/webhooks/enot"
