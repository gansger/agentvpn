from __future__ import annotations

import unittest
from decimal import Decimal

from apps.api.agentvpn_api.payments.enot_webhook import (
    EnotWebhookPayload,
    validate_event_semantics,
    verify_webhook_signature,
    webhook_payload_hash,
)

OFFICIAL_SAMPLE = {
    "credited": "95.50",
    "custom_fields": {"user": 1},
    "invoice_id": "a3e9ff6f-c5c1-3bcd-854e-4bc995b1ae7a",
    "order_id": "c78d8fe9-ab44-3f21-a37a-ce4ca269cb47",
    "pay_service": "card",
    "amount": "100.00",
    "pay_time": "2023-04-06 16:27:59",
    "payer_details": "553691******1279",
    "status": "success",
    "type": 1,
}


class EnotWebhookTest(unittest.TestCase):
    def test_official_signature_example_is_accepted(self) -> None:
        signature = "e582b14dd13f8111711e3cb66a982fd7bff28a0ddece8bde14a34a5bb4449136"

        self.assertTrue(verify_webhook_signature(OFFICIAL_SAMPLE, signature, "example"))
        self.assertFalse(verify_webhook_signature(OFFICIAL_SAMPLE, "0" * 64, "example"))

    def test_payload_hash_is_stable_across_top_level_key_order(self) -> None:
        reversed_payload = dict(reversed(list(OFFICIAL_SAMPLE.items())))

        self.assertEqual(
            webhook_payload_hash(OFFICIAL_SAMPLE),
            webhook_payload_hash(reversed_payload),
        )

    def test_success_semantics_require_payment_type_and_success_code(self) -> None:
        event = EnotWebhookPayload.model_validate(
            {
                "invoice_id": "invoice-1",
                "status": "success",
                "amount": Decimal("499.00"),
                "currency": "RUB",
                "order_id": "payment-1",
                "type": 1,
                "code": 1,
            }
        )
        validate_event_semantics(event)

        invalid = event.model_copy(update={"code": 31})
        with self.assertRaises(ValueError):
            validate_event_semantics(invalid)


if __name__ == "__main__":
    unittest.main()
