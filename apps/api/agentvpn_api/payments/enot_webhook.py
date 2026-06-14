"""Signature verification and idempotent ENOT webhook processing."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.database.locks import acquire_advisory_lock
from apps.api.agentvpn_api.database.models import (
    ActorType,
    AuditLog,
    Payment,
    PaymentStatus,
    PaymentWebhookEvent,
    WebhookProcessingStatus,
)
from apps.api.agentvpn_api.payments.service import PaymentStateError, activate_successful_payment

ENOT_PROVIDER = "enot"


class EnotWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    invoice_id: str = Field(min_length=1, max_length=255)
    status: Literal["success", "fail", "expired", "refund"]
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=10)
    order_id: str = Field(min_length=1, max_length=255)
    event_type: int = Field(alias="type")
    code: int


@dataclass(frozen=True, slots=True)
class WebhookProcessingResult:
    status: Literal["processed", "ignored", "failed"]
    duplicate: bool
    error: str | None = None


def canonical_webhook_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def webhook_payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_webhook_json(payload)).hexdigest()


def verify_webhook_signature(payload: dict[str, Any], signature: str, secret_key: str) -> bool:
    if len(signature) != 64:
        return False
    calculated = hmac.new(
        secret_key.encode(),
        msg=canonical_webhook_json(payload),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature.lower(), calculated)


def validate_event_semantics(event: EnotWebhookPayload) -> None:
    expected = {
        "success": (1, 1),
        "fail": (1, 32),
        "expired": (1, 31),
        "refund": (2, 20),
    }
    if (event.event_type, event.code) != expected[event.status]:
        raise ValueError("ENOT webhook status, type and code do not match")


async def process_enot_webhook(
    session: AsyncSession,
    *,
    raw_payload: dict[str, Any],
    event: EnotWebhookPayload,
    now: datetime | None = None,
) -> WebhookProcessingResult:
    current_time = now or datetime.now(UTC)
    payload_hash = webhook_payload_hash(raw_payload)
    external_event_key = payload_hash
    await acquire_advisory_lock(
        session,
        namespace="enot-webhook",
        entity_id=external_event_key,
    )
    existing = await session.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == ENOT_PROVIDER,
            PaymentWebhookEvent.external_event_key == external_event_key,
        )
    )
    if existing is not None:
        return WebhookProcessingResult(
            status=_result_status(existing.processing_status),
            duplicate=True,
            error=existing.error_message,
        )

    webhook_record = PaymentWebhookEvent(
        provider=ENOT_PROVIDER,
        external_event_key=external_event_key,
        payload_hash=payload_hash,
        signature_valid=True,
        processing_status=WebhookProcessingStatus.RECEIVED,
    )
    session.add(webhook_record)
    await session.flush()

    payment = await session.scalar(
        select(Payment)
        .where(
            Payment.provider == ENOT_PROVIDER,
            Payment.provider_invoice_id == event.invoice_id,
            Payment.order_id == event.order_id,
        )
        .with_for_update()
    )
    if payment is None:
        return await _finish(
            session,
            webhook_record,
            status=WebhookProcessingStatus.IGNORED,
            now=current_time,
            error="Matching ENOT payment was not found",
        )
    if payment.amount != event.amount or payment.currency != event.currency:
        return await _finish(
            session,
            webhook_record,
            status=WebhookProcessingStatus.FAILED,
            now=current_time,
            error="ENOT webhook amount or currency does not match the payment",
        )

    try:
        if event.status == "success":
            await activate_successful_payment(session, payment_id=payment.id, now=current_time)
        elif event.status == "refund":
            if payment.status == PaymentStatus.REFUNDED:
                return await _finish(
                    session,
                    webhook_record,
                    status=WebhookProcessingStatus.IGNORED,
                    now=current_time,
                    error="Payment is already refunded",
                )
            if payment.status != PaymentStatus.SUCCESS:
                raise PaymentStateError("Payment cannot be refunded from its current status")
            payment.status = PaymentStatus.REFUNDED
            payment.refunded_at = current_time
            _add_audit_log(session, payment, action="payment.refunded")
        elif payment.status in {PaymentStatus.CREATED, PaymentStatus.WAITING}:
            payment.status = (
                PaymentStatus.EXPIRED if event.status == "expired" else PaymentStatus.FAILED
            )
            if event.status == "expired":
                payment.expired_at = current_time
            _add_audit_log(session, payment, action=f"payment.{payment.status.value}")
        else:
            return await _finish(
                session,
                webhook_record,
                status=WebhookProcessingStatus.IGNORED,
                now=current_time,
                error="Payment is already in a terminal state",
            )
    except PaymentStateError as exc:
        return await _finish(
            session,
            webhook_record,
            status=WebhookProcessingStatus.FAILED,
            now=current_time,
            error=str(exc),
        )

    return await _finish(
        session,
        webhook_record,
        status=WebhookProcessingStatus.PROCESSED,
        now=current_time,
    )


async def _finish(
    session: AsyncSession,
    record: PaymentWebhookEvent,
    *,
    status: WebhookProcessingStatus,
    now: datetime,
    error: str | None = None,
) -> WebhookProcessingResult:
    record.processing_status = status
    record.processed_at = now
    record.error_message = error
    await session.flush()
    return WebhookProcessingResult(status=_result_status(status), duplicate=False, error=error)


def _add_audit_log(session: AsyncSession, payment: Payment, *, action: str) -> None:
    session.add(
        AuditLog(
            actor_type=ActorType.WEBHOOK,
            actor_id=ENOT_PROVIDER,
            action=action,
            entity_type="payment",
            entity_id=str(payment.id),
            metadata_json={"provider": ENOT_PROVIDER},
        )
    )


def _result_status(
    status: WebhookProcessingStatus,
) -> Literal["processed", "ignored", "failed"]:
    if status == WebhookProcessingStatus.IGNORED:
        return "ignored"
    if status == WebhookProcessingStatus.FAILED:
        return "failed"
    return "processed"
