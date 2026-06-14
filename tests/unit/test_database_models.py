from __future__ import annotations

import unittest
from collections import Counter
from typing import cast

from sqlalchemy import Enum, UniqueConstraint

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

    def test_schema_object_names_are_present_and_unique(self) -> None:
        names: list[str] = []
        for table in Base.metadata.sorted_tables:
            for constraint in table.constraints:
                self.assertIsNotNone(constraint.name, f"Unnamed constraint on {table.name}")
                names.append(str(constraint.name))
            for index in table.indexes:
                self.assertIsNotNone(index.name, f"Unnamed index on {table.name}")
                names.append(str(index.name))

        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        self.assertEqual(duplicates, [])

    def test_composite_unique_constraints_have_explicit_stable_names(self) -> None:
        expected = {
            "uq_vpn_inbounds_server_external_id",
            "uq_vpn_inbounds_server_protocol",
            "uq_xui_bindings_subscription_protocol",
            "uq_payment_webhook_provider_event",
        }
        actual = {
            str(constraint.name)
            for table in Base.metadata.sorted_tables
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint) and len(constraint.columns) > 1
        }

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
