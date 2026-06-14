# Этап 3: тарифы и mock-платежи

Этап 3 добавляет тарифы, идемпотентный checkout, расчёт периода подписки и
`MockPaymentProvider`. Настоящие платежи на этом этапе не принимаются.

## Безопасность production

На production-сервере обязательно оставьте:

```dotenv
ENABLE_MOCK_PAYMENTS=false
```

При `APP_ENV=production` приложение откажется запускаться, если mock-платежи включены.
Реальные продажи будут доступны после интеграции Robokassa на Этапе 4.

## Настройка тарифов

Цены не хранятся в Git и не задаются автоматически. После применения миграций владелец
создаёт тарифы с фактическими ценами:

```bash
docker compose exec api python infrastructure/scripts/upsert_plan.py \
  --name "1 месяц" --duration-days 30 --price ВАША_ЦЕНА --sort-order 10

docker compose exec api python infrastructure/scripts/upsert_plan.py \
  --name "3 месяца" --duration-days 90 --price ВАША_ЦЕНА --sort-order 20

docker compose exec api python infrastructure/scripts/upsert_plan.py \
  --name "12 месяцев" --duration-days 365 --price ВАША_ЦЕНА --sort-order 30
```

Повторный запуск с тем же именем безопасно обновляет тариф. Чтобы временно скрыть тариф,
добавьте `--inactive`.

Проверка:

```bash
curl --fail --silent --show-error "https://ВАШ_ДОМЕН/api/plans"
```

## Mock checkout для staging

Mock checkout разрешён только в development/test окружении:

```dotenv
APP_ENV=test
ENABLE_MOCK_PAYMENTS=true
```

Создание платежа требует авторизованную Telegram-сессию, CSRF-заголовок и уникальный
`Idempotency-Key`. Повтор с тем же пользователем, тарифом и ключом возвращает тот же
платёж. Повторная mock-активация не создаёт вторую подписку и не продлевает её повторно.

После mock-успеха подписка имеет `provisioning_status=pending`. Полностью активной она
станет только после успешной выдачи и проверки обоих клиентов 3x-ui на следующем этапе.

## Обновление APP-SERVER

```bash
cd ~/opt/agent/agentvpn
git pull --ff-only
docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps -a
docker compose logs --no-color --tail=200 migrate
```

Не используйте `docker compose down -v`: постоянные volumes удалять не требуется.
