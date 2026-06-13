from __future__ import annotations

import unittest
from typing import Any

from apps.api.agentvpn_api.auth.sessions import ReplayDetectedError, SessionStore


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, **options: Any) -> bool:
        if options.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        return int(self.values.pop(key, None) is not None)


class SessionStoreTest(unittest.IsolatedAsyncioTestCase):
    def store(self, redis: FakeRedis) -> SessionStore:
        return SessionStore(
            redis,  # type: ignore[arg-type]
            session_secret="s" * 32,
            csrf_secret="c" * 32,
            session_ttl_seconds=3600,
            replay_ttl_seconds=600,
        )

    async def test_session_round_trip_and_delete(self) -> None:
        redis = FakeRedis()
        store = self.store(redis)

        token, created = await store.create(user_id=7, telegram_id=123)
        loaded = await store.get(token)

        self.assertEqual(loaded, created)
        self.assertNotIn(token, " ".join(redis.values.keys()))
        await store.delete(token)
        self.assertIsNone(await store.get(token))

    async def test_replay_digest_can_only_be_claimed_once(self) -> None:
        store = self.store(FakeRedis())

        await store.claim_replay_digest("digest")
        with self.assertRaises(ReplayDetectedError):
            await store.claim_replay_digest("digest")


if __name__ == "__main__":
    unittest.main()
