from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "scripts" / "fetch_xui_openapi.py"
)
SPEC = importlib.util.spec_from_file_location("fetch_xui_openapi", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load fetch_xui_openapi helper")
fetch_xui_openapi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_xui_openapi)


class XuiOpenApiFetchHelperTest(unittest.TestCase):
    def test_load_env_file_reads_values_without_overriding_environment(self) -> None:
        env_path = Path("fixture.env")
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(
                Path,
                "read_text",
                return_value=(
                    "XUI_BASE_URL=https://vpn.example.com\n"
                    "XUI_USERNAME=file-user\n"
                    "# comment\n"
                ),
            ),
            patch.dict(os.environ, {"XUI_USERNAME": "process-user"}, clear=True),
        ):
            fetch_xui_openapi.load_env_file(env_path)

            self.assertEqual(os.environ["XUI_BASE_URL"], "https://vpn.example.com")
            self.assertEqual(os.environ["XUI_USERNAME"], "process-user")

    def test_load_env_file_rejects_invalid_entries(self) -> None:
        env_path = Path("fixture.env")
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="not-an-assignment\n"),
        ):
            with self.assertRaises(ValueError):
                fetch_xui_openapi.load_env_file(env_path)

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
