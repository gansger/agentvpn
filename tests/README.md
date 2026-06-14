# Тесты

Contract-тесты никогда не должны выполнять изменяющие create/delete-операции в production.
Для них требуется явно настроенный staging.

Полный набор Python-проверок:

```bash
python -B -m unittest discover -s tests -p "test_*.py" -v
ruff check .
mypy apps infrastructure tests
```

Тест миграций создаёт отдельный Compose-проект с чистой PostgreSQL в `tmpfs`, выполняет
`upgrade → Stage 3 checkout/idempotency → Stage 4 Robokassa ResultURL/idempotency → downgrade base → upgrade`
и не использует
постоянные volumes:

```bash
sh infrastructure/scripts/test_clean_postgres_migrations.sh
```

Проверка Caddyfile также не подключает production volumes:

```bash
PUBLIC_DOMAIN=example.com sh infrastructure/scripts/validate_caddy.sh
```

HTTPS smoke-тест после деплоя проверяет сертификат и оба health endpoint:

```bash
python infrastructure/scripts/smoke_https_health.py --domain DOMAIN
```
