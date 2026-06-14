"""Authenticated mock checkout and payment status endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import PlainTextResponse

from apps.api.agentvpn_api.database.models import Payment
from apps.api.agentvpn_api.dependencies import (
    database_session,
    mock_payment_provider_from,
    robokassa_payment_provider_from,
    settings_from,
)
from apps.api.agentvpn_api.payments.api_models import (
    CheckoutRequest,
    MockPaymentCompletionResponse,
    PaymentResponse,
)
from apps.api.agentvpn_api.payments.presenters import (
    to_payment_response,
    to_subscription_response,
)
from apps.api.agentvpn_api.payments.robokassa import RobokassaPaymentProviderError
from apps.api.agentvpn_api.payments.robokassa_result import (
    RobokassaResultPayload,
    process_robokassa_result,
    verify_result_signature,
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
MAX_ROBOKASSA_RESULT_BYTES = 64 * 1024


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


@router.post("/api/checkout/robokassa", response_model=PaymentResponse)
async def robokassa_checkout(
    payload: CheckoutRequest,
    request: Request,
    database: DatabaseSession,
    idempotency_key: IdempotencyKey,
) -> PaymentResponse:
    provider = robokassa_payment_provider_from(request)
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
    except RobokassaPaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment provider is temporarily unavailable",
        ) from exc
    return to_payment_response(payment)


@router.get("/api/webhooks/robokassa/result", response_class=PlainTextResponse)
async def robokassa_result_get(
    request: Request,
    database: DatabaseSession,
) -> PlainTextResponse:
    return await _handle_robokassa_result(request, database)


@router.post("/api/webhooks/robokassa/result", response_class=PlainTextResponse)
async def robokassa_result_post(
    request: Request,
    database: DatabaseSession,
) -> PlainTextResponse:
    return await _handle_robokassa_result(request, database)


async def _handle_robokassa_result(
    request: Request,
    database: AsyncSession,
) -> PlainTextResponse:
    settings = settings_from(request)
    if not settings.enable_robokassa_payments or settings.robokassa_password_2 is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        raw_payload = await _robokassa_result_params(request)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Robokassa ResultURL payload",
        ) from exc

    if not verify_result_signature(
        raw_payload,
        password_2=settings.robokassa_password_2.get_secret_value(),
        algorithm=settings.robokassa_hash_algorithm,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    try:
        event = RobokassaResultPayload.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Robokassa ResultURL payload",
        ) from exc

    async with database.begin():
        result = await process_robokassa_result(database, raw_payload=raw_payload, event=event)
    if result.status != "processed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Robokassa ResultURL does not match payment state",
        )
    return PlainTextResponse(f"OK{event.invoice_id}")


async def _robokassa_result_params(request: Request) -> dict[str, str]:
    if len(request.url.query.encode("utf-8")) > MAX_ROBOKASSA_RESULT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="ResultURL query is too large",
        )
    pairs = list(request.query_params.multi_items())
    if request.method == "POST":
        raw_body = await request.body()
        if len(raw_body) > MAX_ROBOKASSA_RESULT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="ResultURL body is too large",
            )
        if raw_body:
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/x-www-form-urlencoded"):
                raise ValueError("Unsupported ResultURL content type")
            pairs.extend(
                parse_qsl(
                    raw_body.decode("utf-8"),
                    keep_blank_values=True,
                    strict_parsing=True,
                )
            )
    params: dict[str, str] = {}
    for key, value in pairs:
        if key in params:
            raise ValueError("Duplicate ResultURL parameter")
        params[key] = value
    return params


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
