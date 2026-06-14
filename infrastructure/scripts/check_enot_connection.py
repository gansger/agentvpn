"""Read-only verification of ENOT credentials and the configured SBP service."""

from __future__ import annotations

import asyncio

import httpx

from apps.api.agentvpn_api.config import AppSettings
from apps.api.agentvpn_api.payments.enot import EnotPaymentProvider


async def check() -> None:
    settings = AppSettings()  # type: ignore[call-arg]
    if (
        not settings.enable_enot_payments
        or settings.enot_shop_id is None
        or settings.enot_secret_key is None
    ):
        raise RuntimeError("Enable ENOT payments and configure ENOT credentials first")

    async with httpx.AsyncClient(
        base_url=str(settings.enot_api_base_url).rstrip("/"),
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
    ) as client:
        provider = EnotPaymentProvider(
            client=client,
            shop_id=settings.enot_shop_id,
            secret_key=settings.enot_secret_key.get_secret_value(),
            webhook_url=settings.enot_webhook_url,
            success_url=settings.public_origin,
            fail_url=settings.public_origin,
            service_code=settings.enot_sbp_service_code,
            expire_minutes=settings.enot_payment_expire_minutes,
        )
        enabled_services = await provider.get_enabled_services()

    if settings.enot_sbp_service_code not in enabled_services:
        raise RuntimeError(
            f"Configured ENOT service {settings.enot_sbp_service_code!r} is not enabled for RUB"
        )
    print(f"ENOT connection OK; RUB service {settings.enot_sbp_service_code!r} is enabled")


if __name__ == "__main__":
    asyncio.run(check())
