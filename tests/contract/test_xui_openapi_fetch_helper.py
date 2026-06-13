from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "scripts" / "fetch_xui_openapi.py"
)
SPEC = importlib.util.spec_from_file_location("fetch_xui_openapi", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load fetch_xui_openapi helper")
fetch_xui_openapi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_xui_openapi)


class XuiOpenApiFetchHelperTest(unittest.TestCase):
    def test_schema_url_preserves_panel_base_path(self) -> None:
        result = fetch_xui_openapi.build_schema_url(
            "https://vpn.example.com/secret-panel/",
            "/panel/api/openapi.json",
        )

        self.assertEqual(
            result,
            "https://vpn.example.com/secret-panel/panel/api/openapi.json",
        )

    def test_transport_requires_https_for_remote_hosts(self) -> None:
        with self.assertRaises(ValueError):
            fetch_xui_openapi.validate_transport("http://vpn.example.com/panel/api/openapi.json")

    def test_transport_allows_local_http_for_discovery(self) -> None:
        fetch_xui_openapi.validate_transport("http://127.0.0.1:2053/panel/api/openapi.json")

    def test_redacted_url_drops_query_and_credentials(self) -> None:
        result = fetch_xui_openapi.redact_url(
            "https://operator:secret@vpn.example.com/panel/api/openapi.json?token=secret"
        )

        self.assertEqual(result, "https://vpn.example.com/panel/api/openapi.json")

    def test_validate_schema_rejects_non_openapi_json(self) -> None:
        with self.assertRaises(ValueError):
            fetch_xui_openapi.validate_schema(b'{"status": "ok"}')


if __name__ == "__main__":
    unittest.main()

