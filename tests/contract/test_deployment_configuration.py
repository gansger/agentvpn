from __future__ import annotations

import unittest
from pathlib import Path

CADDYFILE = Path("infrastructure/reverse-proxy/Caddyfile")
COMPOSE_FILE = Path("docker-compose.yml")
PUBLIC_INDEX = Path("apps/mini-app/public/index.html")
PUBLIC_CSS = Path("apps/mini-app/public/app.css")
PUBLIC_JS = Path("apps/mini-app/public/app.js")
PUBLIC_LOGO = Path("apps/mini-app/public/logo.png")
PUBLIC_INFO = Path("apps/mini-app/public/public-info.js")
PUBLIC_SBP_LOGO = Path("apps/mini-app/public/sbp-logo.svg")
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

    def test_public_homepage_does_not_expose_old_provider_verification(self) -> None:
        content = PUBLIC_INDEX.read_text(encoding="utf-8")
        head = content.split("<head>", maxsplit=1)[1].split("</head>", maxsplit=1)[0]

        self.assertNotIn('name="enot"', head)

    def test_public_site_contains_moderation_and_mini_app_content(self) -> None:
        content = PUBLIC_INDEX.read_text(encoding="utf-8")
        public_info = PUBLIC_INFO.read_text(encoding="utf-8")

        for path in (PUBLIC_CSS, PUBLIC_JS, PUBLIC_LOGO, PUBLIC_INFO, PUBLIC_SBP_LOGO):
            self.assertTrue(path.is_file())
        body = content.split("<body>", maxsplit=1)[1]
        self.assertNotIn("ENOT", body)
        self.assertNotIn("Robokassa", body)
        for text in (
            "Оплата через СБП",
            "Условия оказания услуг",
            "Политика конфиденциальности",
            'data-view="checkout"',
            'data-view="instructions"',
            "Договор публичной оферты",
            "Возврат и отмена",
            "Сроки и регионы оказания услуги",
            "Форма регистрации",
            'data-public-field="inn"',
            'alt="Система быстрых платежей — СБП"',
        ):
            self.assertIn(text, content)
        self.assertIn('document.body.classList.add("telegram-mode")', PUBLIC_JS.read_text("utf-8"))
        self.assertIn("body:not(.telegram-mode) .landing", PUBLIC_CSS.read_text("utf-8"))
        for value in (
            "Магомедов Гасан-Гусейн",
            "Самозанятый, плательщик налога на профессиональный доход",
            "050204720898",
            "367000, РД., г. Махачкала",
            "https://t.me/+927-XyJ49MRlNDU6",
            "+7 964 050-84-90",
            "uu.gg.01@mail.ru",
        ):
            self.assertIn(value, public_info)
        mini_app = content.split('<section class="mini-app"', maxsplit=1)[1].split(
            "</section>", maxsplit=1
        )[0]
        for private_public_value in ("050204720898", "367000"):
            self.assertNotIn(private_public_value, mini_app)
        self.assertIn('id="mini-support-email"', mini_app)
        footer = content.split('<footer class="site-footer"', maxsplit=1)[1]
        for footer_value in (
            'data-public-field="legalName"',
            'data-public-field="inn"',
            'data-public-field="legalAddress"',
            'data-public-field="supportPhone"',
            'data-public-field="supportEmail"',
            'data-public-link="supportTelegramUrl"',
        ):
            self.assertIn(footer_value, footer)
        self.assertNotIn("ID группы", content)
        self.assertNotIn("-5539080426", content)
        self.assertNotIn("Реквизиты и поддержка", content)

    def test_clean_migration_test_cannot_remove_production_volumes(self) -> None:
        compose = MIGRATION_COMPOSE_FILE.read_text(encoding="utf-8")
        script = MIGRATION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("tmpfs:", compose)
        self.assertNotIn("volumes:", compose)
        self.assertNotIn("down -v", script)
        self.assertNotIn("down --volumes", script)

    def test_example_environment_uses_robokassa_sbp_only(self) -> None:
        content = Path(".env.example").read_text(encoding="utf-8")

        self.assertIn("ENABLE_ROBOKASSA_PAYMENTS=false", content)
        self.assertIn("ROBOKASSA_SBP_METHOD=SBP", content)
        self.assertNotIn("ENABLE_ENOT_PAYMENTS", content)


if __name__ == "__main__":
    unittest.main()
