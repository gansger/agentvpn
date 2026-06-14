"""Signature verification and idempotent Robokassa ResultURL processing."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.database.locks import acquire_advisory_lock
from apps.api.agentvpn_api.database.models import (
    Payment,
    PaymentWebhookEvent,
    WebhookProcessingStatus,
)
from apps.api.agentvpn_api.payments.robokassa import result_signature
from apps.api.agentvpn_api.payments.service import PaymentStateError, activate_successful_payment

ROBOKASSA_PROVIDER = "robokassa"


class RobokassaResultPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    out_sum: Decimal = Field(alias="OutSum", ge=0)
    invoice_id: int = Field(alias="InvId", gt=0)
    signature_value: str = Field(alias="SignatureValue", min_length=16, max_length=256)
    order_id: str = Field(alias="Shp_order_id", min_length=1, max_length=255)


@dataclass(frozen=True, slots=True)
class ResultProcessingResult:
    status: Literal["processed", "ignored", "failed"]
    duplicate: bool
    error: str | None = None


def result_payload_hash(payload: dict[str, str]) -> str:
    signed_payload = {
        key: value
        for key, value in payload.items()
        if key in {"OutSum", "InvId", "SignatureValue"} or key.startswith("Shp_")
    }
    canonical = urlencode(sorted(signed_payload.items())).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_result_signature(
    payload: dict[str, str],
    *,
    password_2: str,
    algorithm: str,
) -> bool:
    required = ("OutSum", "InvId", "SignatureValue")
    if any(not payload.get(key) for key in required):
        return False
    shp_params = {key: value for key, value in payload.items() if key.startswith("Shp_")}
    expected = result_signature(
        out_sum=payload["OutSum"],
        invoice_id=payload["InvId"],
        password=password_2,
        shp_params=shp_params,
        algorithm=algorithm,
    )
    return hmac.compare_digest(payload["SignatureValue"].lower(), expected.lower())


async def process_robokassa_result(
    session: AsyncSession,
    *,
    raw_payload: dict[str, str],
    event: RobokassaResultPayload,
    now: datetime | None = None,
) -> ResultProcessingResult:
    current_time = now or datetime.now(UTC)
    payload_hash = result_payload_hash(raw_payload)
    await acquire_advisory_lock(
        session,
        namespace="robokassa-result",
        entity_id=payload_hash,
    )
    existing = await session.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == ROBOKASSA_PROVIDER,
            PaymentWebhookEvent.external_event_key == payload_hash,
        )
    )
    if existing is not None:
        return ResultProcessingResult(
            status=_result_status(existing.processing_status),
            duplicate=True,
            error=existing.error_message,
        )

    record = PaymentWebhookEvent(
        provider=ROBOKASSA_PROVIDER,
        external_event_key=payload_hash,
        payload_hash=payload_hash,
        signature_valid=True,
        processing_status=WebhookProcessingStatus.RECEIVED,
    )
    session.add(record)
    await session.flush()

    payment = await session.scalar(
        select(Payment)
        .where(
            Payment.provider == ROBOKASSA_PROVIDER,
            Payment.provider_invoice_id == str(event.invoice_id),
            Payment.order_id == event.order_id,
        )
        .with_for_update()
    )
    if payment is None:
        return await _finish(
            session,
            record,
            status=WebhookProcessingStatus.IGNORED,
            now=current_time,
            error="Matching Robokassa payment was not found",
        )
    if payment.amount != event.out_sum or payment.currency != "RUB":
        return await _finish(
            session,
            record,
            status=WebhookProcessingStatus.FAILED,
            now=current_time,
            error="Robokassa result amount or currency does not match the payment",
        )
    try:
        await activate_successful_payment(session, payment_id=payment.id, now=current_time)
    except PaymentStateError as exc:
        return await _finish(
            session,
            record,
            status=WebhookProcessingStatus.FAILED,
            now=current_time,
            error=str(exc),
        )
    return await _finish(
        session,
        record,
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
) -> ResultProcessingResult:
    record.processing_status = status
    record.processed_at = now
    record.error_message = error
    await session.flush()
    return ResultProcessingResult(status=_result_status(status), duplicate=False, error=error)


def _result_status(status: WebhookProcessingStatus) -> Literal["processed", "ignored", "failed"]:
    if status == WebhookProcessingStatus.IGNORED:
        return "ignored"
    if status == WebhookProcessingStatus.FAILED:
        return "failed"
    return "processed"
