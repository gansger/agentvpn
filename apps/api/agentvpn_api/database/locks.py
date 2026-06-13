"""PostgreSQL transaction-scoped advisory locks for critical workflows."""

from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def advisory_lock_key(namespace: str, entity_id: str | int) -> int:
    digest = hashlib.sha256(f"{namespace}:{entity_id}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def acquire_advisory_lock(
    session: AsyncSession,
    *,
    namespace: str,
    entity_id: str | int,
) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": advisory_lock_key(namespace, entity_id)},
    )
