from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from urllib.parse import urlencode

from apps.api.agentvpn_api.auth.telegram import (
    TelegramInitDataError,
    validate_telegram_init_data,
)

BOT_TOKEN = "123456:unit-test-token"  # noqa: S105


def signed_init_data(*, auth_date: int, user_id: int = 123, tamper_hash: bool = False) -> str:
    fields = {
        "auth_date": str(auth_date),
        "query_id": "query-1",
        "user": json.dumps(
            {
                "id": user_id,
                "first_name": "Alice",
                "username": "alice",
                "language_code": "ru",
            },
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    fields["hash"] = "0" * 64 if tamper_hash else signature
    return urlencode(fields)


class TelegramAuthTest(unittest.TestCase):
    def test_valid_init_data_is_accepted(self) -> None:
        result = validate_telegram_init_data(
            signed_init_data(auth_date=1_000),
            BOT_TOKEN,
            max_age_seconds=300,
            now=1_100,
        )

        self.assertEqual(result.user.id, 123)
        self.assertEqual(result.query_id, "query-1")
        self.assertEqual(len(result.replay_digest), 64)

    def test_invalid_signature_is_rejected(self) -> None:
        with self.assertRaises(TelegramInitDataError):
            validate_telegram_init_data(
                signed_init_data(auth_date=1_000, tamper_hash=True),
                BOT_TOKEN,
                max_age_seconds=300,
                now=1_100,
            )

    def test_expired_init_data_is_rejected(self) -> None:
        with self.assertRaises(TelegramInitDataError):
            validate_telegram_init_data(
                signed_init_data(auth_date=1_000),
                BOT_TOKEN,
                max_age_seconds=300,
                now=1_301,
            )

    def test_future_init_data_is_rejected(self) -> None:
        with self.assertRaises(TelegramInitDataError):
            validate_telegram_init_data(
                signed_init_data(auth_date=1_031),
                BOT_TOKEN,
                max_age_seconds=300,
                now=1_000,
            )


if __name__ == "__main__":
    unittest.main()
