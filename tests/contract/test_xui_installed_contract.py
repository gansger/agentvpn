from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, ClassVar

SNAPSHOT = Path(__file__).resolve().parents[2] / "docs" / "3x-ui-openapi.json"


class InstalledXuiContractTest(unittest.TestCase):
    document: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_supported_authentication_modes_are_present(self) -> None:
        schemes = self.document["components"]["securitySchemes"]

        self.assertEqual(schemes["bearerAuth"]["scheme"], "bearer")
        self.assertEqual(schemes["cookieAuth"]["name"], "3x-ui")
        self.assertIn("/login", self.document["paths"])

    def test_required_operations_and_methods_are_present(self) -> None:
        expected = {
            "/panel/api/server/status": "get",
            "/panel/api/inbounds/get/{id}": "get",
            "/panel/api/clients/add": "post",
            "/panel/api/clients/update/{email}": "post",
            "/panel/api/clients/{email}/attach": "post",
            "/panel/api/clients/del/{email}": "post",
            "/panel/api/clients/get/{email}": "get",
            "/panel/api/clients/traffic/{email}": "get",
            "/panel/api/clients/links/{email}": "get",
            "/panel/api/clients/onlines": "post",
        }

        for path, method in expected.items():
            with self.subTest(path=path):
                self.assertIn(method, self.document["paths"][path])

    def test_expiry_time_examples_use_milliseconds(self) -> None:
        example = self.document["paths"]["/panel/api/clients/add"]["post"]["requestBody"][
            "content"
        ]["application/json"]["example"]["client"]["expiryTime"]

        self.assertGreaterEqual(example, 1_000_000_000_000)


if __name__ == "__main__":
    unittest.main()
