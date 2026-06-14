# AGentVPN

Production-oriented Telegram-бот и Mini App для продажи VPN-доступа, выдаваемого через
существующую установку 3x-ui. Центральный backend является источником истины. Telegram-бот,
Mini App и панель администратора никогда не обращаются к 3x-ui или ENOT напрямую.

Текущее состояние репозитория соответствует **Этапу 4: интеграция платежей ENOT и СБП**.

## Текущее состояние

- Описаны архитектура, границы доверия и правила владения данными.
- Подготовлена модель угроз и первоначальные меры защиты.
- Зафиксированы архитектурные решения для 3x-ui, платежей и доставки подписки.
- Создана структура монорепозитория.
- Добавлен безопасный загрузчик OpenAPI-схемы установленной панели 3x-ui.
- Добавлена contract-проверка сохранённой OpenAPI-схемы.
- Проект Stitch зафиксирован как источник дизайна Mini App.
- Зафиксировано production-размещение на двух отдельных серверах.
- Реализованы typed 3x-ui API client и `ThreeXUIProvisioningProvider`.
- Для всех создаваемых и обновляемых Hysteria2/VLESS-клиентов принудительно используется
  `flow=xtls-rprx-vision`.
- Реализован FastAPI backend с health/readiness endpoints.
- Реализована проверка Telegram Mini App `initData`, защита от повторного использования,
  Redis-сессии и CSRF.
- Добавлены SQLAlchemy-модели и начальная Alembic-миграция PostgreSQL.
- Добавлен production Docker Compose: PostgreSQL, Redis, миграции, API и Caddy.
- Добавлены `PaymentProvider` и безопасный `MockPaymentProvider` для development/staging.
- Реализованы тарифы, идемпотентный checkout и просмотр статуса платежа.
- Реализован UTC-расчёт создания и продления подписки без повторной активации.
- Добавлена PostgreSQL integration-проверка checkout и повторной обработки успеха.
- Реализован `EnotPaymentProvider`, создающий платежи только через настроенный метод СБП.
- Добавлен подписанный ENOT webhook с идемпотентной активацией подписки и проверкой
  invoice ID, order ID, суммы, валюты и состояния платежа.
- Добавлена read-only проверка доступности СБП в кассе ENOT.
- Реализованы публичный сайт для модерации платёжной системы и адаптивный Telegram
  Mini App по готовым экранам Stitch `Kinetic Shield`.

Endpoints и форматы запросов 3x-ui взяты из OpenAPI фактически установленной панели и
зафиксированы в `docs/3x-ui-openapi.json`.

## Структура репозитория

```text
apps/
  api/                 FastAPI-приложение и фоновые задачи
  bot/                 Telegram-бот на aiogram 3
  mini-app/            Telegram Mini App на React
  admin/               Панель администратора
packages/
  shared/              Общие контракты и сгенерированные клиенты
infrastructure/
  docker/              Описания контейнеров
  reverse-proxy/       Конфигурация Caddy или Nginx
  scripts/             Скрипты эксплуатации и исследования интеграций
docs/
  adr/                 Записи архитектурных решений
  runbooks/            Инструкции по эксплуатации
tests/
  contract/            Проверки контрактов внешних систем
```

## Проверка проекта

Используйте Python 3.12 или новее:

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
python -B infrastructure/scripts/check_python_syntax.py
ruff check .
mypy apps infrastructure tests
```

Интеграционные deployment-проверки используют только одноразовые контейнеры и не
подключают постоянные volumes production-стека:

```bash
sh infrastructure/scripts/test_clean_postgres_migrations.sh
PUBLIC_DOMAIN=example.com sh infrastructure/scripts/validate_caddy.sh
```

После локальной настройки `XUI_BASE_URL` и переменных авторизации:

```powershell
python infrastructure/scripts/fetch_xui_openapi.py
python -B -m unittest discover -s tests -p "test_*.py"
```

Загрузчик запрещает обычный HTTP для удалённых адресов, удаляет credentials из ошибок,
ограничивает размер ответа, проверяет JSON и атомарно сохраняет snapshot схемы. Скрипт
автоматически читает `.env` из корня проекта, не переопределяя переменные окружения,
заданные системой.

## Проверка подключения к 3x-ui

На APP-SERVER создайте Python-окружение и установите проект:

```bash
cd /opt/agentvpn
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
```

Затем выполните безопасную read-only проверку:

```bash
.venv/bin/python infrastructure/scripts/check_xui_connection.py
```

Проверка получает состояние Xray и валидирует настроенные Hysteria2 и VLESS REALITY
inbound. Она не создаёт и не изменяет клиентов.

## Данные, необходимые от владельца

Эти параметры нельзя безопасно определить автоматически. Их следует настраивать локально,
а не отправлять в чат:

- базовый URL 3x-ui и поддерживаемый способ авторизации;
- inbound ID для Hysteria2;
- inbound ID для VLESS REALITY;
- публичный домен;
- токен Telegram-бота;
- ENOT Shop ID и подтверждение наличия активного метода СБП;
- Happ Provider ID, только если проект владеет им и использует его.

Подробности находятся в
[инструкции по ручным действиям Этапа 1](docs/runbooks/stage-1-owner-actions.md) и
[инструкции развёртывания Этапа 2](docs/runbooks/stage-2-app-server-deployment.md), а
настройка тарифов описана в
[инструкции Этапа 3](docs/runbooks/stage-3-plans-and-mock-payments.md) и
[инструкции Этапа 4](docs/runbooks/stage-4-enot-sbp-payments.md).

## Production-размещение

AGentVPN и VPN-инфраструктура размещаются раздельно:

```text
Сервер AGentVPN: 2 vCPU / 4 ГБ RAM / 1 Гбит/с
Сервер VPN в Германии: 2 vCPU / 4 ГБ RAM / 1 Гбит/с / безлимитный трафик
```

Панель 3x-ui принимает управляющие запросы только с фиксированного IP сервера AGentVPN.
Пользовательский VPN-трафик не проходит через сервер AGentVPN.

## HTTPS и проверка после деплоя

Caddy автоматически получает и продлевает TLS-сертификат. Для этого `PUBLIC_DOMAIN`
указывается без `https://` и без пути, DNS A-запись должна указывать на `APP-SERVER`, а
TCP-порты `80` и `443` должны быть открыты. Сертификаты сохраняются в постоянном Docker
volume `caddy_data`.

```bash
curl http://DOMAIN/health/live
curl https://DOMAIN/health/live
curl https://DOMAIN/health/ready
python infrastructure/scripts/smoke_https_health.py --domain DOMAIN
```

Не выполняйте `docker compose down -v` при обычном обновлении: эта команда удаляет
постоянные данные PostgreSQL, Redis и сертификаты Caddy.
