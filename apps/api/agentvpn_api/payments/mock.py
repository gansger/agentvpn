"""In-memory payment provider for development and tests only."""

from __future__ import annotations

import hashlib

from apps.api.agentvpn_api.payments.models import (
    InvoiceRequest,
    ProviderInvoice,
    ProviderPaymentStatus,
)


class MockInvoiceNotFoundError(LookupError):
    """Requested mock invoice does not exist."""


class MockPaymentProvider:
    name = "mock"

    def __init__(self) -> None:
        self._invoices: dict[str, ProviderInvoice] = {}
        self._invoice_ids_by_order: dict[str, str] = {}

    async def create_invoice(self, request: InvoiceRequest) -> ProviderInvoice:
        existing_id = self._invoice_ids_by_order.get(request.order_id)
        if existing_id is not None:
            return self._invoices[existing_id]

        invoice_id = "mock_" + hashlib.sha256(request.order_id.encode()).hexdigest()[:24]
        invoice = ProviderInvoice(
            provider_invoice_id=invoice_id,
            payment_url=f"https://mock-payments.invalid/invoices/{invoice_id}",
            status=ProviderPaymentStatus.WAITING,
            sanitized_payload={"provider": self.name},
        )
        self._invoice_ids_by_order[request.order_id] = invoice_id
        self._invoices[invoice_id] = invoice
        return invoice

    async def get_invoice(self, provider_invoice_id: str) -> ProviderInvoice:
        try:
            return self._invoices[provider_invoice_id]
        except KeyError as exc:
            raise MockInvoiceNotFoundError("Mock invoice does not exist") from exc

    async def mark_success(self, provider_invoice_id: str) -> ProviderInvoice:
        if not provider_invoice_id.startswith("mock_"):
            raise MockInvoiceNotFoundError("Mock invoice does not exist")
        current = self._invoices.get(
            provider_invoice_id,
            ProviderInvoice(
                provider_invoice_id=provider_invoice_id,
                payment_url=f"https://mock-payments.invalid/invoices/{provider_invoice_id}",
                status=ProviderPaymentStatus.WAITING,
                sanitized_payload={"provider": self.name},
            ),
        )
        success = ProviderInvoice(
            provider_invoice_id=current.provider_invoice_id,
            payment_url=current.payment_url,
            status=ProviderPaymentStatus.SUCCESS,
            sanitized_payload=current.sanitized_payload,
        )
        self._invoices[provider_invoice_id] = success
        return success
