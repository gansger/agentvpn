"""Public payment and plan API models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    id: int
    name: str
    duration_days: int
    price: Decimal
    currency: str
    traffic_limit_bytes: int | None
    device_limit: int


class CheckoutRequest(BaseModel):
    plan_id: int = Field(gt=0)


class PaymentResponse(BaseModel):
    id: uuid.UUID
    plan_id: int
    provider: str
    amount: Decimal
    currency: str
    status: str
    payment_url: str | None
    created_at: datetime
    paid_at: datetime | None


class SubscriptionResponse(BaseModel):
    id: int
    plan_id: int
    starts_at: datetime
    expires_at: datetime
    status: str
    provisioning_status: str


class MockPaymentCompletionResponse(BaseModel):
    payment: PaymentResponse
    subscription: SubscriptionResponse
    activated_now: bool


class EnotWebhookResponse(BaseModel):
    status: str
    duplicate: bool
