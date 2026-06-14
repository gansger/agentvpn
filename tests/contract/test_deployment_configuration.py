from __future__ import annotations

import unittest
from pathlib import Path

CADDYFILE = Path("infrastructure/reverse-proxy/Caddyfile")
COMPOSE_FILE = Path("docker-compose.yml")
PUBLIC_INDEX = Path("apps/mini-app/public/index.html")
PUBLIC_CSS = Path("apps/mini-app/public/app.css")
PUBLIC_JS = Path("apps/mini-app/public/app.js")
PUBLIC_LOGO = Path("apps/mini-app/public/logo.png")
MIGRATION_COMPOSE_FILE = Path("infrastructure/testing/migration-compose.yml")
MIGRATION_SCRIPT = Path("infrastructure/scripts/test_clean_postgres_migrations.sh")


class DeploymentConfigurationTest(unittest.TestCase):
    def test_caddyfile_avoids_invalid_email_off_directive(self) -> None:
        content = CADDYFILE.read_text(encoding="utf-8")

        self.assertNotIn("email off", content)
        self.assertIn("{$PUBLIC_DOMAIN}", content)
        self.assertIn("@backend path /api/* /health/*", content)
        self.assertIn("try_files {path} /index.html", content)
        self.assertIn("reverse_proxy api:8000", content)

    def test_compose_keeps_persistent_volumes_and_caddy_healthcheck(self) -> None:
        content = COMPOSE_FILE.read_text(encoding="utf-8")

        for volume in ("postgres_data:", "redis_data:", "caddy_data:", "caddy_config:"):
            self.assertIn(volume, content)
        self.assertIn('"caddy", "validate"', content)
        self.assertIn("./apps/mini-app/public:/srv/agentvpn-public:ro", content)
        self.assertNotIn("down -v", content)

    def test_public_homepage_contains_enot_verification_inside_head(self) -> None:
        content = PUBLIC_INDEX.read_text(encoding="utf-8")
        head = content.split("<head>", maxsplit=1)[1].split("</head>", maxsplit=1)[0]

        self.assertIn('<meta name="enot" content="9bbe7724" />', head)

    def test_public_site_contains_moderation_and_mini_app_content(self) -> None:
        content = PUBLIC_INDEX.read_text(encoding="utf-8")

        for path in (PUBLIC_CSS, PUBLIC_JS, PUBLIC_LOGO):
            self.assertTrue(path.is_file())
        body = content.split("<body>", maxsplit=1)[1]
        self.assertNotIn("ENOT", body)
        for text in (
            "Оплата через СБП",
            "Условия оказания услуг",
            "Политика конфиденциальности",
            'data-view="checkout"',
            'data-view="instructions"',
        ):
            self.assertIn(text, content)

    def test_clean_migration_test_cannot_remove_production_volumes(self) -> None:
        compose = MIGRATION_COMPOSE_FILE.read_text(encoding="utf-8")
        script = MIGRATION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("tmpfs:", compose)
        self.assertNotIn("volumes:", compose)
        self.assertNotIn("down -v", script)
        self.assertNotIn("down --volumes", script)


if __name__ == "__main__":
    unittest.main()
