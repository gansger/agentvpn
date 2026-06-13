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
`POSTGRES_PASSWORD`.

Перед запуском проверьте конфигурацию:

```bash
docker compose config --quiet
docker compose build
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
docker compose logs --tail=100 migrate api caddy
curl --fail --silent "https://ВАШ_ДОМЕН/health/live"
curl --fail --silent "https://ВАШ_ДОМЕН/health/ready"
docker compose exec api python infrastructure/scripts/check_xui_connection.py
```

Ожидаемый ответ `/health/live`: `{"status":"ok"}`. Readiness-проверка должна подтвердить
доступность PostgreSQL и Redis. Проверка 3x-ui является read-only и не меняет клиентов.

## Обновление

```bash
cd /opt/agent/agentvpn
git pull --ff-only
docker compose build
docker compose up -d
docker compose ps
```

Миграции применяются отдельным контейнером до старта новой версии API.

## Диагностика

```bash
docker compose ps
docker compose logs --tail=200 api
docker compose logs --tail=200 migrate
docker compose logs --tail=200 caddy
docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec redis redis-cli ping
```

Не публикуйте наружу порты PostgreSQL, Redis и API. Внешний трафик принимает только Caddy.
