"""Telegram authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.auth.models import (
    AuthResponse,
    PublicUser,
    TelegramAuthRequest,
)
from apps.api.agentvpn_api.auth.sessions import ReplayDetectedError
from apps.api.agentvpn_api.auth.telegram import TelegramInitDataError, validate_telegram_init_data
from apps.api.agentvpn_api.database.models import User, UserStatus
from apps.api.agentvpn_api.dependencies import (
    database_session,
    redis_from,
    session_store_from,
    settings_from,
)
from apps.api.agentvpn_api.rate_limit import allow_request
from apps.api.agentvpn_api.security import require_csrf, require_session
from apps.api.agentvpn_api.users.service import to_public_user, upsert_telegram_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
DatabaseSession = Annotated[AsyncSession, Depends(database_session)]


@router.post("/telegram", response_model=AuthResponse)
async def telegram_auth(
    payload: TelegramAuthRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> AuthResponse:
    settings = settings_from(request)
    redis = redis_from(request)
    client_ip = request.client.host if request.client else "unknown"
    allowed = await allow_request(
        redis,
        key=f"rate:auth:{client_ip}",
        limit=settings.auth_rate_limit_per_minute,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )

    try:
        validated = validate_telegram_init_data(
            payload.init_data,
            settings.telegram_bot_token.get_secret_value(),
            max_age_seconds=settings.telegram_auth_max_age_seconds,
        )
        store = session_store_from(request)
        await store.claim_replay_digest(validated.replay_digest)
    except (TelegramInitDataError, ReplayDetectedError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    async with session.begin():
        user = await upsert_telegram_user(session, validated.user)
        if user.status == UserStatus.BLOCKED:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")

    token, record = await store.create(user_id=user.id, telegram_id=user.telegram_id)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    return AuthResponse(user=to_public_user(user), csrf_token=record.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    session = await require_session(request)
    await require_csrf(request, session)
    token = request.state.session_token
    await session_store_from(request).delete(token)
    settings = settings_from(request)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


@router.get("/me", response_model=PublicUser)
async def me(
    request: Request,
    database: DatabaseSession,
) -> PublicUser:
    session = await require_session(request)
    user = await database.scalar(select(User).where(User.id == session.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return to_public_user(user)
