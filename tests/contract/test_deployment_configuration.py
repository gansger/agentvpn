from __future__ import annotations

import unittest
from pathlib import Path

CADDYFILE = Path("infrastructure/reverse-proxy/Caddyfile")
COMPOSE_FILE = Path("docker-compose.yml")
MIGRATION_COMPOSE_FILE = Path("infrastructure/testing/migration-compose.yml")
MIGRATION_SCRIPT = Path("infrastructure/scripts/test_clean_postgres_migrations.sh")


class DeploymentConfigurationTest(unittest.TestCase):
    def test_caddyfile_avoids_invalid_email_off_directive(self) -> None:
        content = CADDYFILE.read_text(encoding="utf-8")

        self.assertNotIn("email off", content)
        self.assertIn("{$PUBLIC_DOMAIN}", content)
        self.assertIn("reverse_proxy api:8000", content)

    def test_compose_keeps_persistent_volumes_and_caddy_healthcheck(self) -> None:
        content = COMPOSE_FILE.read_text(encoding="utf-8")

        for volume in ("postgres_data:", "redis_data:", "caddy_data:", "caddy_config:"):
            self.assertIn(volume, content)
        self.assertIn('"caddy", "validate"', content)
        self.assertNotIn("down -v", content)

    def test_clean_migration_test_cannot_remove_production_volumes(self) -> None:
        compose = MIGRATION_COMPOSE_FILE.read_text(encoding="utf-8")
        script = MIGRATION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("tmpfs:", compose)
        self.assertNotIn("volumes:", compose)
        self.assertNotIn("down -v", script)
        self.assertNotIn("down --volumes", script)


if __name__ == "__main__":
    unittest.main()
