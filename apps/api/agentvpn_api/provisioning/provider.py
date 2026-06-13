"""Business-facing provisioning interface."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from apps.api.agentvpn_api.provisioning.models import (
    ClientTraffic,
    InboundInfo,
    ProviderHealth,
    ProvisionedClient,
    ProvisioningProtocol,
)


class VpnProvisioningProvider(Protocol):
    async def health_check(self) -> ProviderHealth: ...

    async def get_inbound(
        self,
        inbound_id: int,
        expected_protocol: ProvisioningProtocol,
    ) -> InboundInfo: ...

    async def create_client(
        self,
        *,
        external_email: str,
        telegram_id: int,
        inbound_id: int,
        protocol: ProvisioningProtocol,
        expires_at: datetime,
        traffic_limit_bytes: int | None,
        device_limit: int,
    ) -> ProvisionedClient: ...

    async def update_client(
        self,
        external_email: str,
        *,
        expires_at: datetime | None = None,
        traffic_limit_bytes: int | None = None,
        enabled: bool | None = None,
    ) -> ProvisionedClient: ...

    async def enable_client(self, external_email: str) -> ProvisionedClient: ...

    async def disable_client(self, external_email: str) -> ProvisionedClient: ...

    async def delete_client(self, external_email: str) -> None: ...

    async def get_client(self, external_email: str) -> ProvisionedClient | None: ...

    async def get_client_traffic(self, external_email: str) -> ClientTraffic: ...

    async def get_client_share_uri(
        self,
        external_email: str,
        protocol: ProvisioningProtocol,
    ) -> str: ...

    async def verify_client_exists(self, external_email: str) -> bool: ...

    async def list_online_clients(self) -> list[str]: ...
