from __future__ import annotations

import unittest
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import httpx

from apps.api.agentvpn_api.payments.models import InvoiceRequest, ProviderPaymentStatus
from apps.api.agentvpn_api.payments.robokassa import (
    RobokassaPaymentProvider,
    RobokassaPaymentProviderError,
    payment_signature,
)


class RobokassaPaymentProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_invoice_builds_signed_sbp_only_payment_url(self) -> None:
        async with httpx.AsyncClient(
            base_url="https://auth.robokassa.ru",
            transport=httpx.MockTransport(lambda _: httpx.Response(500)),
        ) as client:
            invoice = await self._provider(client).create_invoice(self._request())

        query = parse_qs(urlparse(invoice.payment_url or "").query)
        self.assertEqual(invoice.status, ProviderPaymentStatus.WAITING)
        self.assertTrue(invoice.provider_invoice_id.isdigit())
        self.assertEqual(query["PaymentMethods"], ["SBP"])
        self.assertEqual(query["Shp_order_id"], ["payment_123"])
        self.assertEqual(query["OutSum"], ["499.00"])
        self.assertEqual(
            query["SignatureValue"],
            [
                payment_signature(
                    merchant_login="merchant",
                    out_sum="499.00",
                    invoice_id=invoice.provider_invoice_id,
                    password="password-1",  # noqa: S106
                    shp_params={"Shp_order_id": "payment_123"},
                    algorithm="sha256",
                )
            ],
        )

    async def test_create_invoice_requires_rubles(self) -> None:
        async with httpx.AsyncClient(base_url="https://auth.robokassa.ru") as client:
            request = self._request()
            request = InvoiceRequest(
                order_id=request.order_id,
                amount=request.amount,
                currency="USD",
                description=request.description,
            )
            with self.assertRaises(RobokassaPaymentProviderError):
                await self._provider(client).create_invoice(request)

    async def test_get_invoice_maps_success_state(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/Merchant/WebService/Service.asmx/OpStateExt")
            return httpx.Response(
                200,
                content=(
                    b"<OperationStateResponse><Result><Code>0</Code></Result>"
                    b"<State><Code>100</Code></State></OperationStateResponse>"
                ),
            )

        async with httpx.AsyncClient(
            base_url="https://auth.robokassa.ru",
            transport=httpx.MockTransport(handler),
        ) as client:
            invoice = await self._provider(client, test_mode=False).get_invoice("123")

        self.assertEqual(invoice.status, ProviderPaymentStatus.SUCCESS)

    async def test_enabled_methods_reads_currency_aliases(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=(
                    b"<CurrenciesList><Result><Code>0</Code></Result><Groups><Group>"
                    b'<Currency Alias="SBP" Label="SBPPSR"/>'
                    b'<Currency Alias="BankCard" Label="BankCardPSR"/>'
                    b"</Group></Groups></CurrenciesList>"
                ),
            )

        async with httpx.AsyncClient(
            base_url="https://auth.robokassa.ru",
            transport=httpx.MockTransport(handler),
        ) as client:
            methods = await self._provider(client).get_enabled_methods()

        self.assertEqual(methods, {"SBP", "BankCard"})

    @staticmethod
    def _provider(
        client: httpx.AsyncClient,
        *,
        test_mode: bool = True,
    ) -> RobokassaPaymentProvider:
        return RobokassaPaymentProvider(
            client=client,
            payment_url="https://auth.robokassa.ru/Merchant/Index.aspx",
            merchant_login="merchant",
            password_1="password-1",  # noqa: S106
            password_2="password-2",  # noqa: S106
            hash_algorithm="sha256",
            sbp_method="SBP",
            test_mode=test_mode,
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
