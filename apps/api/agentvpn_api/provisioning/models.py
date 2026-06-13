"""Provider-neutral provisioning domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProvisioningProtocol(StrEnum):
    HYSTERIA2 = "HYSTERIA2"
    VLESS_REALITY = "VLESS_REALITY"


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    available: bool
    engine_state: str


@dataclass(frozen=True, slots=True)
class InboundInfo:
    external_id: int
    protocol: ProvisioningProtocol
    enabled: bool
    display_name: str


@dataclass(frozen=True, slots=True)
class ProvisionedClient:
    external_email: str
    enabled: bool
    expiry_time_ms: int
    inbound_ids: tuple[int, ...]
    external_sub_id: str | None


@dataclass(frozen=True, slots=True)
class ClientTraffic:
    external_email: str
    enabled: bool
    expiry_time_ms: int
    last_online_ms: int
    total_bytes: int
    upload_bytes: int
    download_bytes: int
