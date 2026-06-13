"""Perform read-only health and inbound validation against the configured 3x-ui panel."""

from __future__ import annotations

import asyncio

from apps.api.agentvpn_api.integrations.xui.client import ThreeXUIApiClient
from apps.api.agentvpn_api.integrations.xui.provider import ThreeXUIProvisioningProvider
from apps.api.agentvpn_api.integrations.xui.settings import XuiProvisioningSettings
from apps.api.agentvpn_api.provisioning.models import ProvisioningProtocol


async def check() -> None:
    settings = XuiProvisioningSettings()  # type: ignore[call-arg]
    async with ThreeXUIApiClient(settings) as client:
        provider = ThreeXUIProvisioningProvider(client)
        health = await provider.health_check()
        hysteria = await provider.get_inbound(
            settings.hysteria2_inbound_id,
            ProvisioningProtocol.HYSTERIA2,
        )
        vless = await provider.get_inbound(
            settings.vless_reality_inbound_id,
            ProvisioningProtocol.VLESS_REALITY,
        )

    print(f"Xray state: {health.engine_state}")
    print(
        f"Hysteria2 inbound: id={hysteria.external_id}, "
        f"enabled={hysteria.enabled}, name={hysteria.display_name}"
    )
    print(
        f"VLESS REALITY inbound: id={vless.external_id}, "
        f"enabled={vless.enabled}, name={vless.display_name}"
    )


if __name__ == "__main__":
    asyncio.run(check())
