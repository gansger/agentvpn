"""Provider-neutral payment domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ProviderPaymentStatus(StrEnum):
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


@dataclass(frozen=True, slots=True)
class InvoiceRequest:
    order_id: str
    amount: Decimal
    currency: str
    description: str


@dataclass(frozen=True, slots=True)
class ProviderInvoice:
    provider_invoice_id: str
    payment_url: str
    status: ProviderPaymentStatus
    sanitized_payload: dict[str, Any] = field(default_factory=dict)
