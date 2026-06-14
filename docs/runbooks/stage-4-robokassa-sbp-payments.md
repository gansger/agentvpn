# Этап 4: платежи Robokassa через СБП

Backend создаёт подписанный hosted checkout Robokassa, ограниченный методом `SBP`.
Подписка активируется только после корректно подписанного ResultURL. Редирект пользователя
на SuccessURL сам по себе доступ не выдаёт.

Официальная документация:

- [быстрый старт](https://docs.robokassa.ru/ru/quick-start);
- [платёжный интерфейс](https://docs.robokassa.ru/ru/pay-interface);
- [уведомления и редиректы](https://docs.robokassa.ru/ru/notifications-and-redirects);
- [XML-интерфейсы](https://docs.robokassa.ru/ru/xml-interfaces).

## Что взять в кабинете Robokassa

- `MerchantLogin`;
- пароль №1 для подписи checkout;
- пароль №2 для проверки ResultURL;
- выбранный алгоритм подписи, совпадающий с `ROBOKASSA_HASH_ALGORITHM`.

Секреты заполняются только в `.env` на APP-SERVER. Не отправляйте их в чат и Git.

## Настройка магазина

Укажите в кабинете Robokassa:

```text
ResultURL:  https://aggvpn05.mooo.com/api/webhooks/robokassa/result
SuccessURL: https://aggvpn05.mooo.com/
FailURL:    https://aggvpn05.mooo.com/
Метод ResultURL: POST
Кодировка: UTF-8
```

## Настройка `.env` на APP-SERVER

Сначала заполните параметры с выключенными платежами:

```dotenv
ENABLE_ROBOKASSA_PAYMENTS=false
ROBOKASSA_PAYMENT_URL=https://auth.robokassa.ru/Merchant/Index.aspx
ROBOKASSA_API_BASE_URL=https://auth.robokassa.ru
ROBOKASSA_MERCHANT_LOGIN=ВАШ_MERCHANT_LOGIN
ROBOKASSA_PASSWORD_1=ВАШ_ПАРОЛЬ_1
ROBOKASSA_PASSWORD_2=ВАШ_ПАРОЛЬ_2
ROBOKASSA_HASH_ALGORITHM=md5
ROBOKASSA_SBP_METHOD=SBP
ROBOKASSA_TEST_MODE=true
```

Алгоритм подписи должен точно совпадать с настройкой магазина. Поддерживаются `md5`,
`sha256` и `sha512`.

## Read-only проверка СБП

Проверка вызывает только `GetCurrencies`, не создаёт платёж и не списывает деньги:

```bash
cd ~/opt/agent/agentvpn
docker compose run --rm -e ENABLE_ROBOKASSA_PAYMENTS=true api \
  python infrastructure/scripts/check_robokassa_connection.py
```

Ожидаемый результат:

```text
Robokassa connection OK; method 'SBP' is enabled
```

## Тестовый и production режим

После успешной проверки включите тестовый режим:

```dotenv
ENABLE_ROBOKASSA_PAYMENTS=true
ROBOKASSA_TEST_MODE=true
```

Проведите тестовую оплату из Mini App и убедитесь, что ResultURL активировал подписку.
После модерации магазина и успешного теста переключите:

```dotenv
ROBOKASSA_TEST_MODE=false
```

Обновите контейнеры без удаления постоянных volumes:

```bash
cd ~/opt/agent/agentvpn
git pull --ff-only
docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps -a
docker compose logs --no-color --tail=200 api
```

Не выполняйте `docker compose down -v`.

## API и безопасность

- `POST /api/checkout/robokassa` требует Telegram-сессию, CSRF и уникальный
  `Idempotency-Key`.
- Checkout передаёт `PaymentMethods=SBP`, поэтому пользователю предлагается СБП.
- `GET|POST /api/webhooks/robokassa/result` проверяет подпись паролем №2.
- До активации сверяются `InvId`, `Shp_order_id`, сумма и локальная валюта RUB.
- Повторный ResultURL отвечает тем же `OK{InvId}`, но не продлевает подписку повторно.
- Неверная подпись отклоняется до записи события в базу.
- Возвраты необходимо обрабатывать отдельной сверкой и административным процессом.

## Проверка после тестовой оплаты

```bash
docker compose logs --no-color --tail=200 api
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "select provider, status, amount, currency, paid_at from payments order by created_at desc limit 5;"
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "select provider, processing_status, signature_valid, received_at from payment_webhook_events order by received_at desc limit 5;"
```

Успешный платёж имеет `provider=robokassa`, `status=success`, а ResultURL-событие:
`processing_status=processed` и `signature_valid=true`.
