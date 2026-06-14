# Развёртывание Этапа 2 на APP-SERVER

Эта инструкция выполняется только на `APP-SERVER`. Панель 3x-ui и пользовательский
VPN-трафик остаются на отдельном `VPN-SERVER`.

## До запуска

1. Направьте A-запись публичного домена на IP `APP-SERVER`.
2. Откройте входящие TCP-порты `22`, `80`, `443` и UDP-порт `443`.
3. Установите Docker Engine с Compose plugin и Git.
4. Разрешите `APP-SERVER` обращаться к HTTPS-адресу панели 3x-ui на `VPN-SERVER`.
5. Ограничьте доступ к панели 3x-ui фиксированным IP-адресом `APP-SERVER`.

## Первый запуск

```bash
sudo mkdir -p /opt/agent
sudo chown "$USER":"$USER" /opt/agent
cd /opt/agent
git clone https://github.com/gansger/agentvpn.git
cd agentvpn
cp .env.example .env
chmod 600 .env
nano .env
```

В `.env` обязательно заполните домен, Telegram-секреты, PostgreSQL, Redis и параметры
доступа к 3x-ui. `DATABASE_URL` должен содержать тот же пароль, что и
`POSTGRES_PASSWORD`. `PUBLIC_DOMAIN` указывается только как домен, без `https://`, пути и
завершающего `/`.

Перед запуском проверьте конфигурацию:

```bash
docker compose config --quiet
PUBLIC_DOMAIN=ВАШ_ДОМЕН sh infrastructure/scripts/validate_caddy.sh
docker compose build --pull
```

Запустите приложение:

```bash
docker compose up -d
docker compose ps
```

Контейнер `migrate` применит миграции Alembic и завершится с кодом `0`. Контейнеры
`postgres`, `redis`, `api` и `caddy` должны быть healthy или running.

## Проверка после запуска

```bash
docker compose ps
docker compose logs --no-color --tail=100 migrate api caddy
curl --fail --silent --show-error "http://ВАШ_ДОМЕН/health/live"
curl --fail --silent --show-error "https://ВАШ_ДОМЕН/health/live"
curl --fail --silent --show-error "https://ВАШ_ДОМЕН/health/ready"
python infrastructure/scripts/smoke_https_health.py --domain ВАШ_ДОМЕН
docker compose exec api python infrastructure/scripts/check_xui_connection.py
```

Ожидаемый ответ `/health/live`: `{"status":"ok"}`. Readiness-проверка должна подтвердить
доступность PostgreSQL и Redis. Проверка 3x-ui является read-only и не меняет клиентов.
Caddy получает и продлевает публичный TLS-сертификат автоматически. Для этого DNS должен
указывать на `APP-SERVER`, TCP-порты `80` и `443` должны быть открыты, а постоянный volume
`caddy_data` должен сохраняться.

## Обновление

```bash
cd /opt/agent/agentvpn
git pull --ff-only
docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps
```

Миграции применяются отдельным контейнером до старта новой версии API.
Не используйте `docker compose down -v`: эта команда удаляет постоянные данные PostgreSQL,
Redis и сертификаты Caddy.

## Диагностика

```bash
docker compose ps
docker compose logs --no-color --tail=200 api
docker compose logs --no-color --tail=200 migrate
docker compose logs --no-color --tail=300 caddy
docker compose exec caddy sh -lc 'echo "PUBLIC_DOMAIN=$PUBLIC_DOMAIN"'
docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec redis redis-cli ping
```

Не публикуйте наружу порты PostgreSQL, Redis и API. Внешний трафик принимает только Caddy.
