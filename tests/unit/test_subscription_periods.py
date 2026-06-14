from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from apps.api.agentvpn_api.subscriptions.periods import calculate_subscription_period


class SubscriptionPeriodTest(unittest.TestCase):
    def test_new_subscription_starts_now(self) -> None:
        now = datetime(2026, 6, 14, tzinfo=UTC)

        period = calculate_subscription_period(now=now, duration_days=30)

        self.assertEqual(period.starts_at, now)
        self.assertEqual(period.expires_at, now + timedelta(days=30))

    def test_active_subscription_extends_from_current_expiry(self) -> None:
        now = datetime(2026, 6, 14, tzinfo=UTC)
        starts_at = now - timedelta(days=5)
        expires_at = now + timedelta(days=25)

        period = calculate_subscription_period(
            now=now,
            duration_days=90,
            current_starts_at=starts_at,
            current_expires_at=expires_at,
        )

        self.assertEqual(period.starts_at, starts_at)
        self.assertEqual(period.expires_at, expires_at + timedelta(days=90))

    def test_expired_subscription_starts_new_period(self) -> None:
        now = datetime(2026, 6, 14, tzinfo=UTC)

        period = calculate_subscription_period(
            now=now,
            duration_days=30,
            current_starts_at=now - timedelta(days=60),
            current_expires_at=now - timedelta(days=30),
        )

        self.assertEqual(period.starts_at, now)
        self.assertEqual(period.expires_at, now + timedelta(days=30))

    def test_naive_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_subscription_period(now=datetime(2026, 6, 14), duration_days=30)


if __name__ == "__main__":
    unittest.main()
