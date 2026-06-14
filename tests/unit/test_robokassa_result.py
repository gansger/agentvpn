from __future__ import annotations

import unittest

from apps.api.agentvpn_api.payments.robokassa import result_signature
from apps.api.agentvpn_api.payments.robokassa_result import (
    result_payload_hash,
    verify_result_signature,
)


class RobokassaResultTest(unittest.TestCase):
    def test_signed_result_is_accepted(self) -> None:
        payload = {
            "OutSum": "499.00",
            "InvId": "123",
            "Shp_order_id": "payment_123",
        }
        payload["SignatureValue"] = result_signature(
            out_sum=payload["OutSum"],
            invoice_id=payload["InvId"],
            password="password-2",  # noqa: S106
            shp_params={"Shp_order_id": payload["Shp_order_id"]},
            algorithm="sha256",
        )

        self.assertTrue(
            verify_result_signature(  # noqa: S106
                payload,
                password_2="password-2",  # noqa: S106
                algorithm="sha256",
            )
        )
        self.assertFalse(
            verify_result_signature(  # noqa: S106
                payload,
                password_2="wrong-password",  # noqa: S106
                algorithm="sha256",
            )
        )

    def test_payload_hash_is_stable_across_parameter_order(self) -> None:
        payload = {
            "OutSum": "499.00",
            "InvId": "123",
            "SignatureValue": "signature",
            "Shp_order_id": "payment_123",
        }
        reversed_payload = dict(reversed(list(payload.items())))

        self.assertEqual(result_payload_hash(payload), result_payload_hash(reversed_payload))

    def test_payload_hash_ignores_unsigned_parameters(self) -> None:
        payload = {
            "OutSum": "499.00",
            "InvId": "123",
            "SignatureValue": "signature",
            "Shp_order_id": "payment_123",
        }

        self.assertEqual(
            result_payload_hash(payload),
            result_payload_hash({**payload, "unsigned_replay_nonce": "attacker-controlled"}),
        )


if __name__ == "__main__":
    unittest.main()
