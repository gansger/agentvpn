from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any, cast

from apps.api.agentvpn_api.integrations.xui.models import (
    REQUIRED_CLIENT_FLOW,
    XuiClientRecord,
    XuiInbound,
    XuiServerStatus,
)
from apps.api.agentvpn_api.integrations.xui.provider import ThreeXUIProvisioningProvider
from apps.api.agentvpn_api.provisioning.models import ProvisioningProtocol


class FakeXuiClient:
    def __init__(self, client: XuiClientRecord | None, inbound_protocol: str = "vless") -> None:
        self.client = client
        self.inbound_protocol = inbound_protocol
        self.created = 0
        self.attached = 0
        self.updated = 0

    async def health_check(self) -> XuiServerStatus:
        return XuiServerStatus(xray={"state": "running"})

    async def get_inbound(self, inbound_id: int) -> XuiInbound:
        security = "tls" if self.inbound_protocol == "hysteria" else "reality"
        network = "udp" if self.inbound_protocol == "hysteria" else "tcp"
        return XuiInbound(
            id=inbound_id,
            enable=True,
            protocol=self.inbound_protocol,
            remark="Germany",
            port=443,
            settings={},
            streamSettings={"security": security, "network": network},
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
            flow=client.flow,
        )

    async def update_client(self, _: str, full_payload: dict[str, object]) -> None:
        self.updated += 1
        if self.client is not None:
            self.client = XuiClientRecord.model_validate(
                {**self.client.model_dump(by_alias=True), **full_payload}
            )


class XuiProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_existing_binding_is_idempotent(self) -> None:
        existing = XuiClientRecord(
            email="tg_1_2_vless",
            enable=True,
            expiryTime=1_767_225_600_000,
            inboundIds=[7],
            flow=REQUIRED_CLIENT_FLOW,
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
        self.assertEqual(fake.updated, 0)

    async def test_existing_unattached_client_is_attached_without_duplicate(self) -> None:
        existing = XuiClientRecord(
            email="tg_1_2_vless",
            enable=True,
            expiryTime=1_767_225_600_000,
            inboundIds=[],
            flow=REQUIRED_CLIENT_FLOW,
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

    async def test_existing_client_flow_is_reconciled(self) -> None:
        existing = XuiClientRecord(
            email="tg_1_2_vless",
            enable=True,
            expiryTime=1_767_225_600_000,
            inboundIds=[7],
            flow="",
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

        self.assertEqual(fake.updated, 1)
        reconciled = cast(XuiClientRecord, fake.client)
        self.assertIsNotNone(reconciled)
        self.assertEqual(reconciled.flow, REQUIRED_CLIENT_FLOW)

    async def test_new_hysteria_and_vless_clients_get_required_flow(self) -> None:
        cases = (
            (ProvisioningProtocol.HYSTERIA2, "hysteria"),
            (ProvisioningProtocol.VLESS_REALITY, "vless"),
        )
        for protocol, inbound_protocol in cases:
            with self.subTest(protocol=protocol):
                fake = FakeXuiClient(None, inbound_protocol=inbound_protocol)
                provider = ThreeXUIProvisioningProvider(fake)  # type: ignore[arg-type]

                await provider.create_client(
                    external_email=f"tg_1_2_{protocol.value.lower()}",
                    telegram_id=1,
                    inbound_id=7,
                    protocol=protocol,
                    expires_at=datetime(2026, 1, 1, tzinfo=UTC),
                    traffic_limit_bytes=None,
                    device_limit=1,
                )

                created = cast(XuiClientRecord, fake.client)
                self.assertIsNotNone(created)
                self.assertEqual(created.flow, REQUIRED_CLIENT_FLOW)


if __name__ == "__main__":
    unittest.main()
