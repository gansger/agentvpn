"""Sellable plan endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.database.models import Plan
from apps.api.agentvpn_api.dependencies import database_session
from apps.api.agentvpn_api.payments.api_models import PlanResponse

router = APIRouter(prefix="/api/plans", tags=["plans"])
DatabaseSession = Annotated[AsyncSession, Depends(database_session)]


@router.get("", response_model=list[PlanResponse])
async def list_plans(database: DatabaseSession) -> list[PlanResponse]:
    plans = (
        await database.scalars(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order, Plan.id)
        )
    ).all()
    return [
        PlanResponse(
            id=plan.id,
            name=plan.name,
            duration_days=plan.duration_days,
            price=plan.price,
            currency=plan.currency,
            traffic_limit_bytes=plan.traffic_limit_bytes,
            device_limit=plan.device_limit,
        )
        for plan in plans
    ]
