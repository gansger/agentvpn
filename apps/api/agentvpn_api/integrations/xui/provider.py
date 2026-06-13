"""Provisioning provider implemented against the installed 3x-ui API."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from apps.api.agentvpn_api.integrations.xui.errors import (
    XuiApiError,
    XuiContractError,
    XuiInboundValidationError,
)
from apps.api.agentvpn_api.integrations.xui.models import (
    REQUIRED_CLIENT_FLOW,
    XuiClientCreate,
    XuiClientRecord,
    XuiClientTraffic,
    XuiInbound,
    XuiServerStatus,
    datetime_to_epoch_ms,
)
from apps.api.agentvpn_api.provisioning.models import (
    ClientTraffic,
    InboundInfo,
    ProviderHealth,
    ProvisionedClient,
    ProvisioningProtocol,
)

EXPECTED_INBOUND = {
    ProvisioningProtocol.HYSTERIA2: ("hysteria", "tls", None),
    ProvisioningProtocol.VLESS_REALITY: ("vless", "reality", "tcp"),
}


class XuiApiClientProtocol(Protocol):
    async def health_check(self) -> XuiServerStatus: ...

    async def get_inbound(self, inbound_id: int) -> XuiInbound: ...

    async def get_client(self, email: str) -> XuiClientRecord | None: ...

    async def attach_client(self, email: str, inbound_ids: list[int]) -> None: ...

    async def create_client(self, client: XuiClientCreate, inbound_ids: list[int]) -> None: ...

    async def update_client(self, email: str, full_payload: dict[str, object]) -> None: ...

    async def delete_client(self, email: str, *, keep_traffic: bool = True) -> None: ...

    async def get_client_traffic(self, email: str) -> XuiClientTraffic: ...

    async def get_client_links(self, email: str) -> list[str]: ...

    async def list_online_clients(self) -> list[str]: ...


class ThreeXUIProvisioningProvider:
    def __init__(self, client: XuiApiClientProtocol) -> None:
        self._client = client

    async def health_check(self) -> ProviderHealth:
        status = await self._client.health_check()
        engine_state = str(status.xray.get("state", "unknown"))
        if engine_state != "running":
            raise XuiApiError("3x-ui is reachable but Xray is not running")
        return ProviderHealth(available=True, engine_state=engine_state)

    async def get_inbound(
        self,
        inbound_id: int,
        expected_protocol: ProvisioningProtocol,
    ) -> InboundInfo:
        inbound = await self._client.get_inbound(inbound_id)
        self._validate_inbound(inbound, expected_protocol)
        return InboundInfo(
            external_id=inbound.id,
            protocol=expected_protocol,
            enabled=inbound.enable,
            display_name=inbound.remark,
        )

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
    ) -> ProvisionedClient:
        await self.health_check()
        await self.get_inbound(inbound_id, protocol)

        existing = await self._client.get_client(external_email)
        if existing is not None:
            if existing.flow != REQUIRED_CLIENT_FLOW:
                await self._client.update_client(
                    external_email,
                    existing.full_update_payload(flow=REQUIRED_CLIENT_FLOW),
                )
            if inbound_id not in existing.inbound_ids:
                await self._client.attach_client(external_email, [inbound_id])
            return self._to_domain_client(await self._verify_binding(external_email, inbound_id))

        client = XuiClientCreate(
            email=external_email,
            expiryTime=datetime_to_epoch_ms(expires_at),
            totalGB=traffic_limit_bytes or 0,
            limitIp=device_limit,
            tgId=telegram_id,
        )
        await self._client.create_client(client, [inbound_id])
        return self._to_domain_client(await self._verify_binding(external_email, inbound_id))

    async def update_client(
        self,
        external_email: str,
        *,
        expires_at: datetime | None = None,
        traffic_limit_bytes: int | None = None,
        enabled: bool | None = None,
    ) -> ProvisionedClient:
        current = await self._require_client(external_email)
        changes: dict[str, object] = {}
        if current.flow != REQUIRED_CLIENT_FLOW:
            changes["flow"] = REQUIRED_CLIENT_FLOW
        if expires_at is not None:
            changes["expiryTime"] = datetime_to_epoch_ms(expires_at)
        if traffic_limit_bytes is not None:
            changes["totalGB"] = traffic_limit_bytes
        if enabled is not None:
            changes["enable"] = enabled
        if not changes:
            return self._to_domain_client(current)

        await self._client.update_client(external_email, current.full_update_payload(**changes))
        return self._to_domain_client(await self._require_client(external_email))

    async def enable_client(self, external_email: str) -> ProvisionedClient:
        return await self.update_client(external_email, enabled=True)

    async def disable_client(self, external_email: str) -> ProvisionedClient:
        return await self.update_client(external_email, enabled=False)

    async def delete_client(self, external_email: str) -> None:
        existing = await self._client.get_client(external_email)
        if existing is None:
            return
        await self._client.delete_client(external_email, keep_traffic=True)

    async def get_client(self, external_email: str) -> ProvisionedClient | None:
        client = await self._client.get_client(external_email)
        return self._to_domain_client(client) if client is not None else None

    async def get_client_traffic(self, external_email: str) -> ClientTraffic:
        traffic = await self._client.get_client_traffic(external_email)
        return ClientTraffic(
            external_email=traffic.email,
            enabled=traffic.enable,
            expiry_time_ms=traffic.expiry_time_ms,
            last_online_ms=traffic.last_online_ms,
            total_bytes=traffic.total_bytes,
            upload_bytes=traffic.upload_bytes,
            download_bytes=traffic.download_bytes,
        )

    async def get_client_share_uri(
        self,
        external_email: str,
        protocol: ProvisioningProtocol,
    ) -> str:
        prefix = {
            ProvisioningProtocol.HYSTERIA2: "hy2://",
            ProvisioningProtocol.VLESS_REALITY: "vless://",
        }[protocol]
        links = await self._client.get_client_links(external_email)
        for link in links:
            if link.lower().startswith(prefix):
                return link
        raise XuiContractError(f"3x-ui did not return the required {protocol.value} share URI")

    async def verify_client_exists(self, external_email: str) -> bool:
        return await self._client.get_client(external_email) is not None

    async def list_online_clients(self) -> list[str]:
        return await self._client.list_online_clients()

    async def _require_client(self, external_email: str) -> XuiClientRecord:
        client = await self._client.get_client(external_email)
        if client is None:
            raise XuiApiError("3x-ui client does not exist")
        return client

    async def _verify_binding(self, external_email: str, inbound_id: int) -> XuiClientRecord:
        client = await self._require_client(external_email)
        if inbound_id not in client.inbound_ids:
            raise XuiContractError("3x-ui client was not attached to the required inbound")
        return client

    @staticmethod
    def _to_domain_client(client: XuiClientRecord) -> ProvisionedClient:
        return ProvisionedClient(
            external_email=client.email,
            enabled=client.enable,
            expiry_time_ms=client.expiry_time_ms,
            inbound_ids=tuple(client.inbound_ids),
            external_sub_id=client.sub_id,
        )

    @staticmethod
    def _validate_inbound(
        inbound: XuiInbound,
        expected_protocol: ProvisioningProtocol,
    ) -> None:
        if not inbound.enable:
            raise XuiInboundValidationError("Configured 3x-ui inbound is disabled")

        protocol, security, network = EXPECTED_INBOUND[expected_protocol]
        actual_security = str(inbound.stream_settings.get("security", "")).lower()
        actual_network = str(inbound.stream_settings.get("network", "")).lower()
        if inbound.protocol.lower() != protocol:
            raise XuiInboundValidationError("Configured inbound has an unexpected protocol")
        if actual_security != security:
            raise XuiInboundValidationError("Configured inbound has unexpected security settings")
        if network is not None and actual_network != network:
            raise XuiInboundValidationError("Configured inbound has an unexpected transport")
