"""User registration and lookup service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.auth.models import PublicUser, TelegramUserData
from apps.api.agentvpn_api.database.locks import acquire_advisory_lock
from apps.api.agentvpn_api.database.models import User, UserStatus


async def upsert_telegram_user(session: AsyncSession, data: TelegramUserData) -> User:
    await acquire_advisory_lock(session, namespace="telegram-user", entity_id=data.id)
    user = await session.scalar(select(User).where(User.telegram_id == data.id).with_for_update())
    if user is None:
        user = User(
            telegram_id=data.id,
            username=data.username,
            first_name=data.first_name,
            language_code=data.language_code,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
    else:
        user.username = data.username
        user.first_name = data.first_name
        user.language_code = data.language_code
    await session.flush()
    return user


def to_public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        language_code=user.language_code,
        status=user.status.value,
    )
