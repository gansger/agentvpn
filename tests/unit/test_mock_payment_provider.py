from __future__ import annotations

import unittest
from decimal import Decimal

from apps.api.agentvpn_api.payments.mock import MockPaymentProvider
from apps.api.agentvpn_api.payments.models import InvoiceRequest, ProviderPaymentStatus
from apps.api.agentvpn_api.payments.service import CheckoutError, scoped_idempotency_key


class MockPaymentProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_invoice_creation_is_idempotent_by_order_id(self) -> None:
        provider = MockPaymentProvider()
        request = InvoiceRequest(
            order_id="payment_123",
            amount=Decimal("499.00"),
            currency="RUB",
            description="Test",
        )

        first = await provider.create_invoice(request)
        second = await provider.create_invoice(request)

        self.assertEqual(first, second)
        self.assertEqual(first.status, ProviderPaymentStatus.WAITING)

    async def test_mock_invoice_can_be_marked_successful(self) -> None:
        provider = MockPaymentProvider()
        created = await provider.create_invoice(
            InvoiceRequest(
                order_id="payment_123",
                amount=Decimal("499.00"),
                currency="RUB",
                description="Test",
            )
        )

        completed = await provider.mark_success(created.provider_invoice_id)

        self.assertEqual(completed.status, ProviderPaymentStatus.SUCCESS)

    async def test_mock_invoice_can_be_completed_after_provider_restart(self) -> None:
        completed = await MockPaymentProvider().mark_success("mock_0123456789abcdef01234567")

        self.assertEqual(completed.status, ProviderPaymentStatus.SUCCESS)

    def test_idempotency_key_is_scoped_and_hashed(self) -> None:
        first = scoped_idempotency_key(1, "checkout-key")
        second = scoped_idempotency_key(2, "checkout-key")

        self.assertNotEqual(first, second)
        self.assertNotIn("checkout-key", first)
        with self.assertRaises(CheckoutError):
            scoped_idempotency_key(1, "bad key")


if __name__ == "__main__":
    unittest.main()
