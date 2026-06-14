"""Business-facing payment provider interface."""

from __future__ import annotations

from typing import Protocol

from apps.api.agentvpn_api.payments.models import InvoiceRequest, ProviderInvoice


class PaymentProvider(Protocol):
    name: str

    async def create_invoice(self, request: InvoiceRequest) -> ProviderInvoice: ...

    async def get_invoice(self, provider_invoice_id: str) -> ProviderInvoice: ...
