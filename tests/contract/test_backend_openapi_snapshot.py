from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path("docs/backend-openapi.json")


class BackendOpenApiSnapshotTest(unittest.TestCase):
    def test_snapshot_contains_stage_4_endpoints(self) -> None:
        document: dict[str, Any] = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        paths = document["paths"]

        self.assertEqual(document["info"]["version"], "0.4.0")
        self.assertIn("/health/live", paths)
        self.assertIn("/health/ready", paths)
        self.assertIn("/api/auth/telegram", paths)
        self.assertIn("/api/auth/logout", paths)
        self.assertIn("/api/auth/me", paths)
        self.assertIn("/api/plans", paths)
        self.assertIn("/api/checkout/mock", paths)
        self.assertIn("/api/checkout/robokassa", paths)
        self.assertIn("/api/webhooks/robokassa/result", paths)
        self.assertIn("/api/payments/{payment_id}", paths)
        self.assertIn("/api/payments/{payment_id}/mock-success", paths)
        self.assertIn("/api/subscription/current", paths)


if __name__ == "__main__":
    unittest.main()
