from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apps.api.agentvpn_api.config import AppSettings

BASE_ENV = {
    "APP_ENV": "test",
    "PUBLIC_DOMAIN": "app.example.com",
    "TELEGRAM_BOT_TOKEN": "123456:test-token",
    "TELEGRAM_WEBHOOK_SECRET": "telegram-webhook-secret-value-0001",
    "SESSION_SECRET": "session-secret-value-for-tests-0001",
    "CSRF_SECRET": "csrf-secret-value-for-tests-0000001",
    "DATABASE_URL": "postgresql+asyncpg://agentvpn:test@postgres:5432/agentvpn",
    "REDIS_URL": "redis://redis:6379/0",
}


class AppSettingsTest(unittest.TestCase):
    def test_comma_separated_environment_lists_are_parsed(self) -> None:
        environment = {
            **BASE_ENV,
            "ADMIN_TELEGRAM_IDS": "1, 2",
            "CORS_ORIGINS": "https://one.example.com/, https://two.example.com",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        self.assertEqual(settings.admin_telegram_ids, (1, 2))
        self.assertEqual(
            settings.cors_origins,
            ("https://one.example.com", "https://two.example.com"),
        )

    def test_single_admin_id_is_parsed(self) -> None:
        with patch.dict(os.environ, {**BASE_ENV, "ADMIN_TELEGRAM_IDS": "1"}, clear=True):
            settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

        self.assertEqual(settings.admin_telegram_ids, (1,))

    def test_mock_payments_are_forbidden_in_production(self) -> None:
        environment = {**BASE_ENV, "APP_ENV": "production", "ENABLE_MOCK_PAYMENTS": "true"}

        with patch.dict(os.environ, environment, clear=True), self.assertRaises(ValueError):
            AppSettings(_env_file=None)  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
