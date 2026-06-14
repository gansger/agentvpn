"""Authenticated subscription status endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.database.models import Subscription, SubscriptionStatus
from apps.api.agentvpn_api.dependencies import database_session
from apps.api.agentvpn_api.payments.api_models import SubscriptionResponse
from apps.api.agentvpn_api.payments.presenters import to_subscription_response
from apps.api.agentvpn_api.security import require_session

router = APIRouter(prefix="/api/subscription", tags=["subscriptions"])
DatabaseSession = Annotated[AsyncSession, Depends(database_session)]


@router.get("/current", response_model=SubscriptionResponse)
async def current_subscription(
    request: Request,
    database: DatabaseSession,
) -> SubscriptionResponse:
    authenticated = await require_session(request)
    subscription = await database.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == authenticated.user_id,
            Subscription.status != SubscriptionStatus.DISABLED,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return to_subscription_response(subscription)
