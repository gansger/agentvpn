from __future__ import annotations

import json
import unittest
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[2] / "docs" / "3x-ui-openapi.json"


class XuiOpenApiSnapshotTest(unittest.TestCase):
    def test_snapshot_is_a_usable_openapi_document_when_present(self) -> None:
        if not SNAPSHOT.exists():
            self.skipTest("real installed 3x-ui OpenAPI snapshot has not been fetched")

        document = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

        self.assertIsInstance(document, dict)
        self.assertTrue(document.get("openapi") or document.get("swagger"))
        self.assertIsInstance(document.get("paths"), dict)
        self.assertGreater(len(document["paths"]), 0)


if __name__ == "__main__":
    unittest.main()

