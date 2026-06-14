"""Exercise Stage 4 Robokassa ResultURL idempotency on disposable PostgreSQL."""

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
from apps.api.agentvpn_api.payments.models import (
    InvoiceRequest,
    ProviderInvoice,
    ProviderPaymentStatus,
)
from apps.api.agentvpn_api.payments.robokassa_result import (
    RobokassaResultPayload,
    process_robokassa_result,
)
from apps.api.agentvpn_api.payments.service import create_checkout


class IntegrationRobokassaProvider:
    name = "robokassa"
    invoice_id = "22770001"

    async def create_invoice(self, request: InvoiceRequest) -> ProviderInvoice:
        return ProviderInvoice(
            provider_invoice_id=self.invoice_id,
            payment_url=f"https://auth.robokassa.ru/Merchant/Index.aspx?InvId={self.invoice_id}",
            status=ProviderPaymentStatus.WAITING,
            sanitized_payload={"provider": self.name, "method": "SBP"},
        )

    async def get_invoice(self, provider_invoice_id: str) -> ProviderInvoice:
        raise NotImplementedError


async def check() -> None:
    settings = AppSettings()  # type: ignore[call-arg]
    database = Database(settings.database_url.get_secret_value(), pool_size=1, max_overflow=0)
    provider = IntegrationRobokassaProvider()
    try:
        async with database.session_factory() as session, session.begin():
            user = User(
                telegram_id=999_000_222,
                first_name="Robokassa Integration",
                status=UserStatus.ACTIVE,
            )
            plan = Plan(
                name="Stage 4 Robokassa integration plan",
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
                idempotency_key="stage4-robokassa-checkout-key",
            )
            payment_id = payment.id
            order_id = payment.order_id

        raw_payload = {
            "OutSum": "599.00",
            "InvId": provider.invoice_id,
            "SignatureValue": "integration-signature",
            "Shp_order_id": order_id,
        }
        event = RobokassaResultPayload.model_validate(raw_payload)
        now = datetime(2026, 6, 14, 12, tzinfo=UTC)

        async with database.session_factory() as session, session.begin():
            first = await process_robokassa_result(
                session,
                raw_payload=raw_payload,
                event=event,
                now=now,
            )
        async with database.session_factory() as session, session.begin():
            duplicate = await process_robokassa_result(
                session,
                raw_payload=raw_payload,
                event=event,
                now=now,
            )
        if first.status != "processed" or first.duplicate or not duplicate.duplicate:
            raise RuntimeError("Robokassa ResultURL processing was not idempotent")

        async with database.session_factory() as session:
            stored_payment = await session.get(Payment, payment_id)
            if stored_payment is None:
                raise RuntimeError("Robokassa payment disappeared after ResultURL processing")
            events = await session.scalar(
                select(func.count())
                .select_from(PaymentWebhookEvent)
                .where(PaymentWebhookEvent.provider == "robokassa")
            )
            subscriptions = await session.scalar(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.user_id == stored_payment.user_id)
            )
            if stored_payment.status != PaymentStatus.SUCCESS or events != 1 or subscriptions != 1:
                raise RuntimeError("Robokassa ResultURL did not activate exactly one subscription")
        print("Stage 4 Robokassa ResultURL idempotency OK")
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(check())
