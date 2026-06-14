from __future__ import annotations

import unittest
from decimal import Decimal

import httpx

from apps.api.agentvpn_api.payments.enot import (
    EnotPaymentProvider,
    EnotPaymentProviderError,
)
from apps.api.agentvpn_api.payments.models import InvoiceRequest, ProviderPaymentStatus


class EnotPaymentProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_invoice_requests_sbp_and_returns_payment_url(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/invoice/create")
            self.assertEqual(request.headers["x-api-key"], "secret")
            payload = request.read()
            self.assertIn(b'"include_service":["sbp"]', payload)
            self.assertIn(b'"hook_url":"https://app.example.com/api/webhooks/enot"', payload)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "invoice-1",
                        "amount": "499.00",
                        "currency": "RUB",
                        "url": "https://enot.io/pay/invoice-1",
                        "expired": "2026-06-14 15:00:00",
                    },
                    "status": 200,
                    "status_check": True,
                },
            )

        async with httpx.AsyncClient(
            base_url="https://api.enot.io",
            transport=httpx.MockTransport(handler),
        ) as client:
            provider = self._provider(client)
            invoice = await provider.create_invoice(self._request())

        self.assertEqual(invoice.provider_invoice_id, "invoice-1")
        self.assertEqual(invoice.status, ProviderPaymentStatus.WAITING)
        self.assertEqual(invoice.payment_url, "https://enot.io/pay/invoice-1")

    async def test_create_invoice_rejects_mismatched_provider_amount(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "invoice-1",
                        "amount": "1.00",
                        "currency": "RUB",
                        "url": "https://enot.io/pay/invoice-1",
                    },
                    "status": 200,
                    "status_check": True,
                },
            )

        async with httpx.AsyncClient(
            base_url="https://api.enot.io",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(EnotPaymentProviderError):
                await self._provider(client).create_invoice(self._request())

    async def test_get_invoice_maps_provider_status(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["invoice_id"], "invoice-1")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "invoice_id": "invoice-1",
                        "status": "success",
                        "pay_service": "sbp",
                    },
                    "status": 200,
                    "status_check": True,
                },
            )

        async with httpx.AsyncClient(
            base_url="https://api.enot.io",
            transport=httpx.MockTransport(handler),
        ) as client:
            invoice = await self._provider(client).get_invoice("invoice-1")

        self.assertEqual(invoice.status, ProviderPaymentStatus.SUCCESS)

    async def test_enabled_services_only_include_enabled_rub_tariffs(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "tariffs": [
                            {"service": "sbp", "currency": "RUB", "status": "enabled"},
                            {"service": "card", "currency": "RUB", "status": "disabled"},
                            {"service": "card", "currency": "USD", "status": "enabled"},
                        ]
                    },
                    "status": 200,
                    "status_check": True,
                },
            )

        async with httpx.AsyncClient(
            base_url="https://api.enot.io",
            transport=httpx.MockTransport(handler),
        ) as client:
            services = await self._provider(client).get_enabled_services()

        self.assertEqual(services, {"sbp"})

    @staticmethod
    def _provider(client: httpx.AsyncClient) -> EnotPaymentProvider:
        return EnotPaymentProvider(
            client=client,
            shop_id="shop-id",
            secret_key="secret",  # noqa: S106
            webhook_url="https://app.example.com/api/webhooks/enot",
            success_url="https://app.example.com",
            fail_url="https://app.example.com",
            service_code="sbp",
            expire_minutes=30,
        )

    @staticmethod
    def _request() -> InvoiceRequest:
        return InvoiceRequest(
            order_id="payment_123",
            amount=Decimal("499.00"),
            currency="RUB",
            description="AGentVPN: 1 month",
        )


if __name__ == "__main__":
    unittest.main()
