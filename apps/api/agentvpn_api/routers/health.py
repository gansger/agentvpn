"""Liveness and dependency-aware readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text

from apps.api.agentvpn_api.dependencies import redis_from

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    try:
        async with request.app.state.database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await redis_from(request).ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dependencies are unavailable",
        ) from exc
    return {"status": "ready"}
