"""Mapping database payment entities to public API models."""

from __future__ import annotations

from apps.api.agentvpn_api.database.models import Payment, Subscription
from apps.api.agentvpn_api.payments.api_models import PaymentResponse, SubscriptionResponse


def to_payment_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        plan_id=payment.plan_id,
        provider=payment.provider,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status.value,
        payment_url=payment.payment_url,
        created_at=payment.created_at,
        paid_at=payment.paid_at,
    )


def to_subscription_response(subscription: Subscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=subscription.id,
        plan_id=subscription.plan_id,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
        status=subscription.status.value,
        provisioning_status=subscription.provisioning_status.value,
    )
