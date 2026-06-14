# Docker

Production Compose запускает PostgreSQL, Redis, миграции, API и Caddy. PostgreSQL, Redis
и сертификаты Caddy хранятся в постоянных volumes.

Обычное обновление:

```bash
docker compose build --pull
docker compose up -d --remove-orphans
```

Не используйте `docker compose down -v`: флаг `-v` удаляет постоянные данные.
