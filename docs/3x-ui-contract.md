# Контракт установленной панели 3x-ui

- OpenAPI: `3.0.3`
- API title: `3X-UI Panel API`
- API version: `3.x`
- Snapshot SHA-256:
  `0523e83a1428a350c7f139d6f0add63dd8fc1d185aecfc44d711273103ee7e32`

## Авторизация

Все `/panel/api/*` endpoints поддерживают:

1. API token через `Authorization: Bearer <token>` — основной способ.
2. Session cookie `3x-ui`, получаемую через `POST /login` — fallback.

API token является полноправным административным credential и должен храниться только в
секретах APP-SERVER.

## Используемые endpoints

| Операция | Endpoint | Retry |
|---|---|---|
| Health check | `GET /panel/api/server/status` | безопасный |
| Получить inbound | `GET /panel/api/inbounds/get/{id}` | безопасный |
| Создать клиента | `POST /panel/api/clients/add` | запрещён |
| Получить клиента | `GET /panel/api/clients/get/{email}` | безопасный |
| Обновить клиента | `POST /panel/api/clients/update/{email}` | запрещён |
| Привязать inbound | `POST /panel/api/clients/{email}/attach` | запрещён |
| Удалить клиента | `POST /panel/api/clients/del/{email}` | запрещён |
| Получить трафик | `GET /panel/api/clients/traffic/{email}` | безопасный |
| Получить share URI | `GET /panel/api/clients/links/{email}` | безопасный |
| Получить online-клиентов | `POST /panel/api/clients/onlines` | безопасный |

## Подтверждённые особенности

- `expiryTime` использует Unix timestamp в миллисекундах UTC.
- `totalGB` фактически передаётся в байтах.
- Создание клиента принимает `{client, inboundIds}`.
- Протокольные secrets могут генерироваться сервером при создании.
- Обновление заменяет запись клиента, поэтому адаптер сначала читает существующую запись
  и сохраняет её поля.
- `links/{email}` возвращает готовые URI, которые имеют приоритет перед ручной сборкой.
- Удаление выполняется с `keepTraffic=1`, чтобы сохранить историю трафика.

## Безопасная live-проверка

После установки Python-зависимостей на APP-SERVER:

```bash
python3 infrastructure/scripts/check_xui_connection.py
```

Скрипт выполняет только read-only операции: health check и проверку двух настроенных
inbound. Он не создаёт и не изменяет клиентов.
