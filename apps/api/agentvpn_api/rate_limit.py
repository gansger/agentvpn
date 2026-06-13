"""Small Redis-backed fixed-window limiter for sensitive endpoints."""

from __future__ import annotations

from redis.asyncio import Redis


async def allow_request(redis: Redis, *, key: str, limit: int, window_seconds: int) -> bool:
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    return bool(current <= limit)
