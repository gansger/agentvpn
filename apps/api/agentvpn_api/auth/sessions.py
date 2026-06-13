"""Opaque Redis-backed user sessions and replay protection."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from redis.asyncio import Redis

from apps.api.agentvpn_api.auth.models import SessionRecord


class ReplayDetectedError(ValueError):
    """The same Telegram initData has already been accepted."""


class SessionStore:
    def __init__(
        self,
        redis: Redis,
        *,
        session_secret: str,
        csrf_secret: str,
        session_ttl_seconds: int,
        replay_ttl_seconds: int,
    ) -> None:
        self._redis = redis
        self._session_secret = session_secret.encode()
        self._csrf_secret = csrf_secret.encode()
        self._session_ttl_seconds = session_ttl_seconds
        self._replay_ttl_seconds = replay_ttl_seconds

    def _session_key(self, token: str) -> str:
        digest = hmac.new(self._session_secret, token.encode(), hashlib.sha256).hexdigest()
        return f"session:{digest}"

    def _csrf_token(self, session_token: str) -> str:
        nonce = secrets.token_urlsafe(24)
        signature = hmac.new(
            self._csrf_secret,
            f"{session_token}:{nonce}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{nonce}.{signature}"

    async def claim_replay_digest(self, replay_digest: str) -> None:
        claimed = await self._redis.set(
            f"telegram-replay:{replay_digest}",
            "1",
            ex=self._replay_ttl_seconds,
            nx=True,
        )
        if not claimed:
            raise ReplayDetectedError("Telegram initData has already been used")

    async def create(self, *, user_id: int, telegram_id: int) -> tuple[str, SessionRecord]:
        token = secrets.token_urlsafe(32)
        record = SessionRecord(
            user_id=user_id,
            telegram_id=telegram_id,
            csrf_token=self._csrf_token(token),
            created_at=int(time.time()),
        )
        await self._redis.set(
            self._session_key(token),
            record.model_dump_json(),
            ex=self._session_ttl_seconds,
        )
        return token, record

    async def get(self, token: str) -> SessionRecord | None:
        raw = await self._redis.get(self._session_key(token))
        if raw is None:
            return None
        return SessionRecord.model_validate_json(raw)

    async def delete(self, token: str) -> None:
        await self._redis.delete(self._session_key(token))
