# AGentVPN

Production-oriented Telegram-бот и Mini App для продажи VPN-доступа, выдаваемого через
существующую установку 3x-ui. Центральный backend является источником истины. Telegram-бот,
Mini App и панель администратора никогда не обращаются к 3x-ui или ENOT напрямую.

Текущее состояние репозитория соответствует **Этапу 1: архитектура и исследование
интеграций**.

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

Endpoints и форматы запросов 3x-ui не придумывались. Перед реализацией
`ThreeXUIProvisioningProvider` файл `docs/3x-ui-openapi.json` должен быть получен из
фактически установленной панели.

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

## Проверка Этапа 1

Используйте Python 3.12 или новее:

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
python -B infrastructure/scripts/check_python_syntax.py
```

После того как владелец локально настроит `XUI_BASE_URL` и переменные авторизации:

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
[инструкции по ручным действиям Этапа 1](docs/runbooks/stage-1-owner-actions.md).

## Production-размещение

AGentVPN и VPN-инфраструктура размещаются раздельно:

```text
Сервер AGentVPN: 2 vCPU / 4 ГБ RAM / 1 Гбит/с
Сервер VPN в Германии: 2 vCPU / 4 ГБ RAM / 1 Гбит/с / безлимитный трафик
```

Панель 3x-ui принимает управляющие запросы только с фиксированного IP сервера AGentVPN.
Пользовательский VPN-трафик не проходит через сервер AGentVPN.
