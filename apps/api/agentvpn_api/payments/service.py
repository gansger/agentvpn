"""Idempotent checkout and successful-payment activation."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.database.locks import acquire_advisory_lock
from apps.api.agentvpn_api.database.models import (
    ActorType,
    AuditLog,
    Payment,
    PaymentStatus,
    Plan,
    ProvisioningStatus,
    Subscription,
    SubscriptionStatus,
)
from apps.api.agentvpn_api.payments.models import InvoiceRequest
from apps.api.agentvpn_api.payments.provider import PaymentProvider
from apps.api.agentvpn_api.subscriptions.periods import calculate_subscription_period

IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class CheckoutError(ValueError):
    """Base checkout validation error."""


class PlanUnavailableError(CheckoutError):
    """Selected plan is absent or disabled."""


class IdempotencyConflictError(CheckoutError):
    """Idempotency key was reused for a different operation."""


class PaymentStateError(ValueError):
    """Payment cannot transition to the requested state."""


@dataclass(frozen=True, slots=True)
class ActivationResult:
    payment: Payment
    subscription: Subscription
    activated_now: bool


def scoped_idempotency_key(user_id: int, key: str) -> str:
    if not IDEMPOTENCY_PATTERN.fullmatch(key):
        raise CheckoutError("Idempotency-Key must contain 8-128 safe characters")
    return hashlib.sha256(f"{user_id}:{key}".encode()).hexdigest()


async def create_checkout(
    session: AsyncSession,
    *,
    provider: PaymentProvider,
    user_id: int,
    plan_id: int,
    idempotency_key: str,
) -> Payment:
    scoped_key = scoped_idempotency_key(user_id, idempotency_key)
    await acquire_advisory_lock(session, namespace="checkout", entity_id=scoped_key)

    existing = await session.scalar(
        select(Payment).where(Payment.idempotency_key == scoped_key).with_for_update()
    )
    if existing is not None:
        if (
            existing.user_id != user_id
            or existing.plan_id != plan_id
            or existing.provider != provider.name
        ):
            raise IdempotencyConflictError("Idempotency-Key was reused for another checkout")
        return existing

    plan = await session.scalar(select(Plan).where(Plan.id == plan_id, Plan.is_active.is_(True)))
    if plan is None:
        raise PlanUnavailableError("Plan is unavailable")

    payment_id = uuid.uuid4()
    payment = Payment(
        id=payment_id,
        user_id=user_id,
        plan_id=plan.id,
        provider=provider.name,
        order_id=f"payment_{payment_id.hex}",
        amount=plan.price,
        currency=plan.currency,
        status=PaymentStatus.CREATED,
        idempotency_key=scoped_key,
    )
    session.add(payment)
    await session.flush()

    invoice = await provider.create_invoice(
        InvoiceRequest(
            order_id=payment.order_id,
            amount=payment.amount,
            currency=payment.currency,
            description=f"AGentVPN: {plan.name}",
        )
    )
    payment.provider_invoice_id = invoice.provider_invoice_id
    payment.payment_url = invoice.payment_url
    payment.status = PaymentStatus.WAITING
    payment.provider_payload = invoice.sanitized_payload
    await session.flush()
    return payment


async def activate_successful_payment(
    session: AsyncSession,
    *,
    payment_id: uuid.UUID,
    user_id: int | None = None,
    now: datetime | None = None,
) -> ActivationResult:
    current_time = now or datetime.now(UTC)
    await acquire_advisory_lock(session, namespace="payment-activation", entity_id=str(payment_id))
    payment = await session.scalar(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    )
    if payment is None or (user_id is not None and payment.user_id != user_id):
        raise PaymentStateError("Payment does not exist")

    if payment.status == PaymentStatus.SUCCESS and payment.subscription_id is not None:
        subscription = await session.get(Subscription, payment.subscription_id)
        if subscription is None:
            raise PaymentStateError("Payment references a missing subscription")
        return ActivationResult(payment=payment, subscription=subscription, activated_now=False)
    if payment.status not in {PaymentStatus.CREATED, PaymentStatus.WAITING}:
        raise PaymentStateError("Payment cannot be activated from its current status")

    plan = await session.get(Plan, payment.plan_id)
    if plan is None or payment.amount != plan.price or payment.currency != plan.currency:
        raise PaymentStateError("Payment amount or currency does not match the plan")

    subscription = await session.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == payment.user_id,
            Subscription.status.in_([SubscriptionStatus.PENDING, SubscriptionStatus.ACTIVE]),
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
        .with_for_update()
    )
    if subscription is None:
        period = calculate_subscription_period(now=current_time, duration_days=plan.duration_days)
        subscription = Subscription(
            user_id=payment.user_id,
            plan_id=plan.id,
            starts_at=period.starts_at,
            expires_at=period.expires_at,
            status=SubscriptionStatus.PENDING,
            provisioning_status=ProvisioningStatus.PENDING,
        )
        session.add(subscription)
        await session.flush()
    else:
        period = calculate_subscription_period(
            now=current_time,
            duration_days=plan.duration_days,
            current_starts_at=subscription.starts_at,
            current_expires_at=subscription.expires_at,
        )
        subscription.plan_id = plan.id
        subscription.starts_at = period.starts_at
        subscription.expires_at = period.expires_at
        subscription.provisioning_status = ProvisioningStatus.PENDING

    payment.status = PaymentStatus.SUCCESS
    payment.paid_at = current_time
    payment.subscription_id = subscription.id
    session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id="mock-payment",
            action="payment.activated",
            entity_type="payment",
            entity_id=str(payment.id),
            metadata_json={"subscription_id": subscription.id, "provider": payment.provider},
        )
    )
    await session.flush()
    return ActivationResult(payment=payment, subscription=subscription, activated_now=True)
