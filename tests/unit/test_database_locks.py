from __future__ import annotations

import unittest

from apps.api.agentvpn_api.database.locks import advisory_lock_key


class DatabaseLocksTest(unittest.TestCase):
    def test_lock_keys_are_stable_and_namespaced(self) -> None:
        first = advisory_lock_key("provisioning", 42)

        self.assertEqual(first, advisory_lock_key("provisioning", 42))
        self.assertNotEqual(first, advisory_lock_key("payment", 42))
        self.assertGreaterEqual(first, -(2**63))
        self.assertLess(first, 2**63)


if __name__ == "__main__":
    unittest.main()
