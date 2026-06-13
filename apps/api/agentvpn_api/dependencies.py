"""FastAPI dependency accessors."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.agentvpn_api.auth.sessions import SessionStore
from apps.api.agentvpn_api.config import AppSettings
from apps.api.agentvpn_api.database.session import Database


def settings_from(request: Request) -> AppSettings:
    return cast(AppSettings, request.app.state.settings)


def redis_from(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


def session_store_from(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.session_store)


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = cast(Database, request.app.state.database)
    async with database.session_factory() as session:
        yield session
