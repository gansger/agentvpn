"""Exercise Stage 4 ENOT webhook idempotency on disposable PostgreSQL."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select

from apps.api.agentvpn_api.config import AppSettings
from apps.api.agentvpn_api.database.models import (
    Payment,
    PaymentStatus,
    PaymentWebhookEvent,
    Plan,
    Subscription,
    User,
    UserStatus,
)
from apps.api.agentvpn_api.database.session import Database
from apps.api.agentvpn_api.payments.enot_webhook import (
    EnotWebhookPayload,
    process_enot_webhook,
    validate_event_semantics,
)
from apps.api.agentvpn_api.payments.models import (
    InvoiceRequest,
    ProviderInvoice,
    ProviderPaymentStatus,
)
from apps.api.agentvpn_api.payments.service import create_checkout


class IntegrationEnotProvider:
    name = "enot"
    invoice_id = "d2277ec2-b9a9-43e6-907f-68e13ec225ef"

    async def create_invoice(self, request: InvoiceRequest) -> ProviderInvoice:
        return ProviderInvoice(
            provider_invoice_id=self.invoice_id,
            payment_url=f"https://enot.io/pay/{self.invoice_id}",
            status=ProviderPaymentStatus.WAITING,
            sanitized_payload={"provider": self.name, "service": "sbp"},
        )

    async def get_invoice(self, provider_invoice_id: str) -> ProviderInvoice:
        raise NotImplementedError


async def check() -> None:
    settings = AppSettings()  # type: ignore[call-arg]
    database = Database(settings.database_url.get_secret_value(), pool_size=1, max_overflow=0)
    provider = IntegrationEnotProvider()
    try:
        async with database.session_factory() as session, session.begin():
            user = User(
                telegram_id=999_000_222,
                first_name="ENOT Integration",
                status=UserStatus.ACTIVE,
            )
            plan = Plan(
                name="Stage 4 ENOT integration plan",
                duration_days=30,
                price=Decimal("599.00"),
                currency="RUB",
                device_limit=1,
                is_active=True,
                sort_order=2,
            )
            session.add_all([user, plan])
            await session.flush()
            payment = await create_checkout(
                session,
                provider=provider,
                user_id=user.id,
                plan_id=plan.id,
                idempotency_key="stage4-enot-checkout-key",
            )
            payment_id = payment.id
            order_id = payment.order_id

        raw_payload = {
            "invoice_id": provider.invoice_id,
            "status": "success",
            "amount": "599.00",
            "currency": "RUB",
            "order_id": order_id,
            "custom_fields": {"order_id": order_id},
            "type": 1,
            "code": 1,
            "pay_time": "2026-06-14 15:00:00",
            "pay_service": "sbp",
            "credited": "599.00",
        }
        event = EnotWebhookPayload.model_validate(raw_payload)
        validate_event_semantics(event)
        now = datetime(2026, 6, 14, 12, tzinfo=UTC)

        async with database.session_factory() as session, session.begin():
            first = await process_enot_webhook(
                session,
                raw_payload=raw_payload,
                event=event,
                now=now,
            )
        async with database.session_factory() as session, session.begin():
            duplicate = await process_enot_webhook(
                session,
                raw_payload=raw_payload,
                event=event,
                now=now,
            )
        if first.status != "processed" or first.duplicate or not duplicate.duplicate:
            raise RuntimeError("ENOT webhook processing was not idempotent")

        async with database.session_factory() as session:
            stored_payment = await session.get(Payment, payment_id)
            if stored_payment is None:
                raise RuntimeError("ENOT payment disappeared after webhook processing")
            events = await session.scalar(
                select(func.count())
                .select_from(PaymentWebhookEvent)
                .where(PaymentWebhookEvent.provider == "enot")
            )
            subscriptions = await session.scalar(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.user_id == stored_payment.user_id)
            )
            if stored_payment.status != PaymentStatus.SUCCESS or events != 1 or subscriptions != 1:
                raise RuntimeError("ENOT webhook did not activate exactly one subscription")
        print("Stage 4 ENOT webhook idempotency OK")
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(check())
