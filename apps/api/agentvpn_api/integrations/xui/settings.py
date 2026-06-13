"""3x-ui settings loaded from environment variables or the server .env file."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.api.agentvpn_api.integrations.xui.errors import XuiConfigurationError


class XuiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="XUI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: AnyHttpUrl
    api_token: SecretStr | None = None
    username: str | None = None
    password: SecretStr | None = None
    two_factor_code: SecretStr | None = None
    request_timeout_seconds: float = Field(default=10, gt=0, le=60)
    verify_tls: bool = True
    safe_retry_attempts: int = Field(default=3, ge=1, le=5)
    circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    circuit_reset_seconds: float = Field(default=30, ge=1, le=300)

    @field_validator("api_token", "password", "two_factor_code", mode="before")
    @classmethod
    def empty_secret_to_none(cls, value: Any) -> Any:
        return None if value == "" else value

    @field_validator("username", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_auth_and_transport(self) -> XuiSettings:
        has_token = self.api_token is not None
        has_session_credentials = self.username is not None and self.password is not None
        if not has_token and not has_session_credentials:
            raise XuiConfigurationError(
                "Configure XUI_API_TOKEN or both XUI_USERNAME and XUI_PASSWORD"
            )

        parts = urlsplit(str(self.base_url))
        is_local = parts.hostname in {"127.0.0.1", "localhost", "::1"}
        if parts.scheme != "https" and not is_local:
            raise XuiConfigurationError("Remote XUI_BASE_URL must use HTTPS")
        if not self.verify_tls and not is_local:
            raise XuiConfigurationError("XUI_VERIFY_TLS=false is allowed only for localhost")
        return self

    @property
    def normalized_base_url(self) -> str:
        return str(self.base_url).rstrip("/") + "/"


class XuiProvisioningSettings(XuiSettings):
    hysteria2_inbound_id: int = Field(gt=0)
    vless_reality_inbound_id: int = Field(gt=0)
