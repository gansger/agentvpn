"""Typed models derived from docs/3x-ui-openapi.json."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

REQUIRED_CLIENT_FLOW = "xtls-rprx-vision"


class ApiEnvelope[T](BaseModel):
    model_config = ConfigDict(extra="allow")

    success: bool
    msg: str | None = None
    obj: T | None = None


class XuiInbound(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    enable: bool
    protocol: str
    remark: str
    port: int
    settings: dict[str, Any] = Field(default_factory=dict)
    stream_settings: dict[str, Any] = Field(default_factory=dict, alias="streamSettings")


class XuiClientRecord(BaseModel):
    """Flexible client record returned by the installed central clients API."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    email: str
    enable: bool
    expiry_time_ms: int = Field(alias="expiryTime")
    total_bytes: int = Field(default=0, alias="totalGB")
    ip_limit: int = Field(default=0, alias="limitIp")
    telegram_id: int = Field(default=0, alias="tgId")
    inbound_ids: list[int] = Field(default_factory=list, alias="inboundIds")
    sub_id: str | None = Field(default=None, alias="subId")
    uuid: str | None = None
    auth: str | None = None
    password: str | None = None
    flow: str | None = None
    comment: str | None = None
    group: str | None = None
    reset: int | None = None
    security: str | None = None

    def full_update_payload(self, **changes: object) -> dict[str, object]:
        """Preserve writable fields and secrets when the panel replaces a client row."""
        payload = self.model_dump(by_alias=True, exclude_none=True)
        for read_only in ("inboundIds", "traffic", "createdAt", "updatedAt"):
            payload.pop(read_only, None)

        database_id = payload.get("id")
        if isinstance(database_id, int):
            payload.pop("id", None)

        payload.update(changes)
        return payload


class XuiClientCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str
    enable: bool = True
    expiry_time_ms: int = Field(alias="expiryTime")
    total_bytes: int = Field(default=0, alias="totalGB")
    ip_limit: int = Field(default=0, alias="limitIp")
    telegram_id: int = Field(default=0, alias="tgId")
    flow: str = REQUIRED_CLIENT_FLOW
    comment: str | None = None

    @field_validator("expiry_time_ms", "total_bytes", "ip_limit")
    @classmethod
    def require_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("3x-ui numeric limits must not be negative")
        return value


class XuiClientTraffic(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    email: str
    enable: bool
    expiry_time_ms: int = Field(alias="expiryTime")
    inbound_id: int = Field(alias="inboundId")
    last_online_ms: int = Field(alias="lastOnline")
    total_bytes: int = Field(alias="total")
    upload_bytes: int = Field(alias="up")
    download_bytes: int = Field(alias="down")


class XuiServerStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    cpu: float | None = None
    xray: dict[str, Any] = Field(default_factory=dict)


def datetime_to_epoch_ms(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return int(value.astimezone(UTC).timestamp() * 1000)
