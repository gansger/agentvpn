"""Read-only verification that the configured Robokassa merchant exposes SBP."""

from __future__ import annotations

import asyncio

import httpx

from apps.api.agentvpn_api.config import AppSettings
from apps.api.agentvpn_api.payments.robokassa import RobokassaPaymentProvider


async def check() -> None:
    settings = AppSettings()  # type: ignore[call-arg]
    if (
        not settings.enable_robokassa_payments
        or settings.robokassa_merchant_login is None
        or settings.robokassa_password_1 is None
        or settings.robokassa_password_2 is None
    ):
        raise RuntimeError("Enable Robokassa payments and configure credentials first")

    async with httpx.AsyncClient(
        base_url=str(settings.robokassa_api_base_url).rstrip("/"),
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
    ) as client:
        provider = RobokassaPaymentProvider(
            client=client,
            payment_url=str(settings.robokassa_payment_url),
            merchant_login=settings.robokassa_merchant_login,
            password_1=settings.robokassa_password_1.get_secret_value(),
            password_2=settings.robokassa_password_2.get_secret_value(),
            hash_algorithm=settings.robokassa_hash_algorithm,
            sbp_method=settings.robokassa_sbp_method,
            test_mode=settings.robokassa_test_mode,
        )
        enabled_methods = await provider.get_enabled_methods()

    if settings.robokassa_sbp_method not in enabled_methods:
        raise RuntimeError(
            f"Configured Robokassa method {settings.robokassa_sbp_method!r} is not enabled"
        )
    print(f"Robokassa connection OK; method {settings.robokassa_sbp_method!r} is enabled")


if __name__ == "__main__":
    asyncio.run(check())
