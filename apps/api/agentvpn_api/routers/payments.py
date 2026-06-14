"""Authenticated mock checkout and payment status endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.database.models import Payment
from apps.api.agentvpn_api.dependencies import (
    database_session,
    enot_payment_provider_from,
    mock_payment_provider_from,
    settings_from,
)
from apps.api.agentvpn_api.payments.api_models import (
    CheckoutRequest,
    EnotWebhookResponse,
    MockPaymentCompletionResponse,
    PaymentResponse,
)
from apps.api.agentvpn_api.payments.enot import EnotPaymentProviderError
from apps.api.agentvpn_api.payments.enot_webhook import (
    EnotWebhookPayload,
    process_enot_webhook,
    validate_event_semantics,
    verify_webhook_signature,
)
from apps.api.agentvpn_api.payments.presenters import (
    to_payment_response,
    to_subscription_response,
)
from apps.api.agentvpn_api.payments.service import (
    CheckoutError,
    IdempotencyConflictError,
    PaymentStateError,
    activate_successful_payment,
    create_checkout,
)
from apps.api.agentvpn_api.security import require_csrf, require_session

router = APIRouter(tags=["payments"])
DatabaseSession = Annotated[AsyncSession, Depends(database_session)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
EnotSignature = Annotated[str, Header(alias="x-api-sha256-signature")]
MAX_ENOT_WEBHOOK_BYTES = 64 * 1024


@router.post("/api/checkout/mock", response_model=PaymentResponse)
async def mock_checkout(
    payload: CheckoutRequest,
    request: Request,
    database: DatabaseSession,
    idempotency_key: IdempotencyKey,
) -> PaymentResponse:
    settings = settings_from(request)
    if not settings.enable_mock_payments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    authenticated = await require_session(request)
    await require_csrf(request, authenticated)

    try:
        async with database.begin():
            payment = await create_checkout(
                database,
                provider=mock_payment_provider_from(request),
                user_id=authenticated.user_id,
                plan_id=payload.plan_id,
                idempotency_key=idempotency_key,
            )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CheckoutError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_payment_response(payment)


@router.post("/api/checkout/enot", response_model=PaymentResponse)
async def enot_checkout(
    payload: CheckoutRequest,
    request: Request,
    database: DatabaseSession,
    idempotency_key: IdempotencyKey,
) -> PaymentResponse:
    provider = enot_payment_provider_from(request)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    authenticated = await require_session(request)
    await require_csrf(request, authenticated)

    try:
        async with database.begin():
            payment = await create_checkout(
                database,
                provider=provider,
                user_id=authenticated.user_id,
                plan_id=payload.plan_id,
                idempotency_key=idempotency_key,
            )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CheckoutError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EnotPaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment provider is temporarily unavailable",
        ) from exc
    return to_payment_response(payment)


@router.post("/api/webhooks/enot", response_model=EnotWebhookResponse)
async def enot_webhook(
    request: Request,
    database: DatabaseSession,
    signature: EnotSignature,
) -> EnotWebhookResponse:
    settings = settings_from(request)
    if not settings.enable_enot_payments or settings.enot_webhook_additional_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    raw_body = await request.body()
    if len(raw_body) > MAX_ENOT_WEBHOOK_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook body is too large",
        )
    try:
        raw_payload = json.loads(raw_body)
        if not isinstance(raw_payload, dict):
            raise ValueError
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body must be a JSON object",
        ) from exc

    if not verify_webhook_signature(
        raw_payload,
        signature,
        settings.enot_webhook_additional_key.get_secret_value(),
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    try:
        event = EnotWebhookPayload.model_validate(raw_payload)
        validate_event_semantics(event)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ENOT webhook",
        ) from exc

    async with database.begin():
        result = await process_enot_webhook(database, raw_payload=raw_payload, event=event)
    if result.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ENOT webhook does not match payment state",
        )
    return EnotWebhookResponse(status=result.status, duplicate=result.duplicate)


@router.get("/api/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: uuid.UUID,
    request: Request,
    database: DatabaseSession,
) -> PaymentResponse:
    authenticated = await require_session(request)
    payment = await database.scalar(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == authenticated.user_id)
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return to_payment_response(payment)


@router.post(
    "/api/payments/{payment_id}/mock-success",
    response_model=MockPaymentCompletionResponse,
)
async def complete_mock_payment(
    payment_id: uuid.UUID,
    request: Request,
    database: DatabaseSession,
) -> MockPaymentCompletionResponse:
    settings = settings_from(request)
    if not settings.enable_mock_payments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    authenticated = await require_session(request)
    await require_csrf(request, authenticated)

    async with database.begin():
        payment = await database.scalar(
            select(Payment).where(
                Payment.id == payment_id, Payment.user_id == authenticated.user_id
            )
        )
        if payment is None or payment.provider != "mock" or payment.provider_invoice_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        provider_invoice_id = payment.provider_invoice_id

    await mock_payment_provider_from(request).mark_success(provider_invoice_id)
    try:
        async with database.begin():
            result = await activate_successful_payment(
                database,
                payment_id=payment_id,
                user_id=authenticated.user_id,
            )
    except PaymentStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MockPaymentCompletionResponse(
        payment=to_payment_response(result.payment),
        subscription=to_subscription_response(result.subscription),
        activated_now=result.activated_now,
    )
