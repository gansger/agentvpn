from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from apps.api.agentvpn_api.integrations.xui.models import (
    XuiClientRecord,
    XuiInbound,
    XuiServerStatus,
)
from apps.api.agentvpn_api.integrations.xui.provider import ThreeXUIProvisioningProvider
from apps.api.agentvpn_api.provisioning.models import ProvisioningProtocol


class FakeXuiClient:
    def __init__(self, client: XuiClientRecord | None) -> None:
        self.client = client
        self.created = 0
        self.attached = 0

    async def health_check(self) -> XuiServerStatus:
        return XuiServerStatus(xray={"state": "running"})

    async def get_inbound(self, inbound_id: int) -> XuiInbound:
        return XuiInbound(
            id=inbound_id,
            enable=True,
            protocol="vless",
            remark="Germany",
            port=443,
            settings={},
            streamSettings={"security": "reality", "network": "tcp"},
        )

    async def get_client(self, _: str) -> XuiClientRecord | None:
        return self.client

    async def attach_client(self, _: str, inbound_ids: list[int]) -> None:
        self.attached += 1
        if self.client is not None:
            self.client.inbound_ids.extend(inbound_ids)

    async def create_client(self, client: Any, inbound_ids: list[int]) -> None:
        self.created += 1
        self.client = XuiClientRecord(
            email=client.email,
            enable=True,
            expiryTime=client.expiry_time_ms,
            inboundIds=inbound_ids,
        )


class XuiProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_existing_binding_is_idempotent(self) -> None:
        existing = XuiClientRecord(
            email="tg_1_2_vless",
            enable=True,
            expiryTime=1_767_225_600_000,
            inboundIds=[7],
        )
        fake = FakeXuiClient(existing)
        provider = ThreeXUIProvisioningProvider(fake)  # type: ignore[arg-type]

        result = await provider.create_client(
            external_email="tg_1_2_vless",
            telegram_id=1,
            inbound_id=7,
            protocol=ProvisioningProtocol.VLESS_REALITY,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            traffic_limit_bytes=None,
            device_limit=1,
        )

        self.assertEqual(result.external_email, existing.email)
        self.assertEqual(fake.created, 0)
        self.assertEqual(fake.attached, 0)

    async def test_existing_unattached_client_is_attached_without_duplicate(self) -> None:
        existing = XuiClientRecord(
            email="tg_1_2_vless",
            enable=True,
            expiryTime=1_767_225_600_000,
            inboundIds=[],
        )
        fake = FakeXuiClient(existing)
        provider = ThreeXUIProvisioningProvider(fake)  # type: ignore[arg-type]

        await provider.create_client(
            external_email="tg_1_2_vless",
            telegram_id=1,
            inbound_id=7,
            protocol=ProvisioningProtocol.VLESS_REALITY,
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            traffic_limit_bytes=None,
            device_limit=1,
        )

        self.assertEqual(fake.created, 0)
        self.assertEqual(fake.attached, 1)


if __name__ == "__main__":
    unittest.main()
