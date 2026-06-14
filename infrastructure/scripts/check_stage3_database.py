"""Exercise Stage 3 checkout idempotency on the disposable PostgreSQL test database."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select

from apps.api.agentvpn_api.config import AppSettings
from apps.api.agentvpn_api.database.models import Payment, Plan, Subscription, User, UserStatus
from apps.api.agentvpn_api.database.session import Database
from apps.api.agentvpn_api.payments.mock import MockPaymentProvider
from apps.api.agentvpn_api.payments.service import activate_successful_payment, create_checkout


async def check() -> None:
    settings = AppSettings()  # type: ignore[call-arg]
    database = Database(settings.database_url.get_secret_value(), pool_size=1, max_overflow=0)
    provider = MockPaymentProvider()
    try:
        async with database.session_factory() as session, session.begin():
            user = User(
                telegram_id=999_000_111,
                first_name="Integration",
                status=UserStatus.ACTIVE,
            )
            plan = Plan(
                name="Stage 3 integration plan",
                duration_days=30,
                price=Decimal("499.00"),
                currency="RUB",
                device_limit=1,
                is_active=True,
                sort_order=1,
            )
            session.add_all([user, plan])
            await session.flush()
            user_id = user.id
            plan_id = plan.id

        async with database.session_factory() as session, session.begin():
            first = await create_checkout(
                session,
                provider=provider,
                user_id=user_id,
                plan_id=plan_id,
                idempotency_key="integration-checkout-key",
            )
            second = await create_checkout(
                session,
                provider=provider,
                user_id=user_id,
                plan_id=plan_id,
                idempotency_key="integration-checkout-key",
            )
            if first.id != second.id:
                raise RuntimeError("Idempotent checkout created duplicate payments")
            payment_id = first.id

        now = datetime(2026, 6, 14, tzinfo=UTC)
        async with database.session_factory() as session, session.begin():
            first_activation = await activate_successful_payment(
                session,
                payment_id=payment_id,
                user_id=user_id,
                now=now,
            )
            repeated_activation = await activate_successful_payment(
                session,
                payment_id=payment_id,
                user_id=user_id,
                now=now,
            )
            if not first_activation.activated_now or repeated_activation.activated_now:
                raise RuntimeError("Repeated activation was not idempotent")

        async with database.session_factory() as session:
            payments = await session.scalar(select(func.count()).select_from(Payment))
            subscriptions = await session.scalar(select(func.count()).select_from(Subscription))
            if payments != 1 or subscriptions != 1:
                raise RuntimeError("Checkout integration created duplicate database records")
        print("Stage 3 PostgreSQL checkout idempotency OK")
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(check())
