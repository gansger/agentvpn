from __future__ import annotations

import unittest
from typing import cast

from sqlalchemy import Enum

from apps.api.agentvpn_api.database.base import Base
from apps.api.agentvpn_api.database.models import User, UserStatus


class DatabaseModelsTest(unittest.TestCase):
    def test_required_tables_are_registered(self) -> None:
        expected = {
            "users",
            "plans",
            "subscriptions",
            "payments",
            "vpn_servers",
            "vpn_inbounds",
            "xui_client_bindings",
            "happ_subscription_tokens",
            "payment_webhook_events",
            "audit_logs",
        }

        self.assertEqual(set(Base.metadata.tables), expected)

    def test_enum_persists_stable_lowercase_values(self) -> None:
        enum_type = cast(Enum, User.__table__.c.status.type)

        self.assertIsInstance(enum_type, Enum)
        self.assertEqual(enum_type.enums, ["active", "blocked"])
        self.assertEqual(UserStatus.ACTIVE.value, "active")


if __name__ == "__main__":
    unittest.main()
