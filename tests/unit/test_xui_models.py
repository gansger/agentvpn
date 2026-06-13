from __future__ import annotations

import unittest
from datetime import UTC, datetime

from apps.api.agentvpn_api.integrations.xui.models import (
    XuiClientRecord,
    datetime_to_epoch_ms,
)


class XuiModelsTest(unittest.TestCase):
    def test_datetime_to_epoch_ms_uses_utc_milliseconds(self) -> None:
        value = datetime(2026, 1, 1, tzinfo=UTC)

        self.assertEqual(datetime_to_epoch_ms(value), 1_767_225_600_000)

    def test_datetime_to_epoch_ms_rejects_naive_datetime(self) -> None:
        with self.assertRaises(ValueError):
            datetime_to_epoch_ms(datetime(2026, 1, 1))

    def test_full_update_payload_preserves_protocol_secrets(self) -> None:
        client = XuiClientRecord.model_validate(
            {
                "id": 42,
                "uuid": "secret-uuid",
                "auth": "secret-auth",
                "email": "tg_1_2_hysteria2",
                "enable": True,
                "expiryTime": 1_767_225_600_000,
                "totalGB": 0,
                "limitIp": 1,
                "tgId": 1,
                "inboundIds": [3],
                "createdAt": 1,
                "updatedAt": 2,
            }
        )

        payload = client.full_update_payload(enable=False)

        self.assertEqual(payload["uuid"], "secret-uuid")
        self.assertEqual(payload["auth"], "secret-auth")
        self.assertFalse(payload["enable"])
        self.assertNotIn("id", payload)
        self.assertNotIn("inboundIds", payload)
        self.assertNotIn("createdAt", payload)


if __name__ == "__main__":
    unittest.main()

