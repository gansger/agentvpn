# Этап 4: платежи ENOT через СБП

Этап 4 добавляет создание платежей ENOT с разрешённым методом СБП и обработку
подписанных webhook. Подписка активируется только после подтверждённого webhook ENOT.
Редирект пользователя после оплаты сам по себе доступ не выдаёт.

Официальная документация ENOT:

- [проверка подлинности](https://docs.enot.io/e/new/authentication);
- [создание платежа](https://docs.enot.io/e/new/create-invoice);
- [webhook оплаты](https://docs.enot.io/e/new/payment-webhook);
- [формирование подписи webhook](https://docs.enot.io/e/new/webhook);
- [список методов оплаты](https://docs.enot.io/e/new/payments-methods-list).

## Что взять в кабинете ENOT

В разделе кассы и интеграции получите:

- идентификатор кассы;
- секретный ключ кассы для запросов API;
- дополнительный ключ кассы для проверки webhook.

Не отправляйте эти значения в чат и не добавляйте их в Git.

## Настройка `.env` на APP-SERVER

Сначала оставьте платежи выключенными и заполните параметры:

```dotenv
ENABLE_ENOT_PAYMENTS=false
ENOT_API_BASE_URL=https://api.enot.io
ENOT_SHOP_ID=ВАШ_ID_КАССЫ
ENOT_SECRET_KEY=ВАШ_СЕКРЕТНЫЙ_КЛЮЧ
ENOT_WEBHOOK_ADDITIONAL_KEY=ВАШ_ДОПОЛНИТЕЛЬНЫЙ_КЛЮЧ
ENOT_SBP_SERVICE_CODE=sbp
ENOT_PAYMENT_EXPIRE_MINUTES=30
```

В production разрешены коды `sbp` и `p2p_sbp`. Используйте `sbp`, если ENOT не указал
для вашей кассы другой активный код.

## Read-only проверка подключения

Проверка обращается только к списку доступных тарифов ENOT. Она не создаёт платёж и не
списывает деньги:

```bash
cd ~/opt/agent/agentvpn
docker compose run --rm -e ENABLE_ENOT_PAYMENTS=true api \
  python infrastructure/scripts/check_enot_connection.py
```

Ожидаемый результат:

```text
ENOT connection OK; RUB service 'sbp' is enabled
```

Если сервис не активен, включите СБП для кассы через поддержку или кабинет ENOT.

## Webhook и включение платежей

Backend передаёт при каждом создании платежа приоритетный webhook URL:

```text
https://aggvpn05.mooo.com/api/webhooks/enot
```

Этот же URL рекомендуется указать в настройках кассы ENOT. После успешной read-only
проверки измените:

```dotenv
ENABLE_ENOT_PAYMENTS=true
```

Затем обновите контейнеры без удаления постоянных volumes:

```bash
cd ~/opt/agent/agentvpn
git pull --ff-only
docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps -a
docker compose logs --no-color --tail=200 api
```

Не выполняйте `docker compose down -v`.

## API и правила безопасности

- `POST /api/checkout/enot` требует Telegram-сессию, CSRF и уникальный
  `Idempotency-Key`.
- ENOT получает `include_service: ["sbp"]`, поэтому страница оплаты предлагает СБП.
- `POST /api/webhooks/enot` проверяет HMAC-SHA256 из заголовка
  `x-api-sha256-signature`.
- До активации сверяются invoice ID, order ID, сумма, валюта, статус, тип и код события.
- Повторный webhook не продлевает подписку повторно.
- Неверная подпись отклоняется до записи события в базу.
- Возврат переводит платёж в `refunded`; автоматическое отключение VPN будет добавлено
  вместе с оркестрацией provisioning.

## Проверка после ручного тестового платежа

Создайте минимальный разрешённый платёж через Mini App или API. После оплаты проверьте:

```bash
docker compose logs --no-color --tail=200 api
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "select provider, status, amount, currency, paid_at from payments order by created_at desc limit 5;"
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "select provider, processing_status, signature_valid, received_at from payment_webhook_events order by received_at desc limit 5;"
```

Успешный платёж должен иметь `provider=enot`, `status=success`, а webhook-событие —
`processing_status=processed` и `signature_valid=true`.
