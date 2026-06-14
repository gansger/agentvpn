"""Authenticated mock checkout and payment status endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.database.models import Payment
from apps.api.agentvpn_api.dependencies import (
    database_session,
    mock_payment_provider_from,
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
