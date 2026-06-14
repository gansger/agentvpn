from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from infrastructure.scripts.smoke_https_health import check_https_health, validate_domain


class HttpsHealthSmokeTest(unittest.TestCase):
    def test_domain_must_not_contain_scheme_path_or_port(self) -> None:
        for invalid in (
            "https://app.example.com",
            "app.example.com/",
            "app.example.com:443",
            "app example.com",
            "",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_domain(invalid)

    def test_live_and_ready_are_checked_over_https(self) -> None:
        live = MagicMock()
        live.__enter__.return_value.read.return_value = b'{"status":"ok"}'
        ready = MagicMock()
        ready.__enter__.return_value.read.return_value = b'{"status":"ready"}'

        with patch(
            "infrastructure.scripts.smoke_https_health.urlopen",
            side_effect=[live, ready],
        ) as mocked:
            check_https_health("app.example.com")

        urls = [call.args[0].full_url for call in mocked.call_args_list]
        self.assertEqual(
            urls,
            [
                "https://app.example.com/health/live",
                "https://app.example.com/health/ready",
            ],
        )


if __name__ == "__main__":
    unittest.main()
