"""Create or update one sellable plan without embedding prices in source control."""

from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal

from sqlalchemy import select

from apps.api.agentvpn_api.config import AppSettings
from apps.api.agentvpn_api.database.locks import acquire_advisory_lock
from apps.api.agentvpn_api.database.models import Plan
from apps.api.agentvpn_api.database.session import Database


async def upsert_plan(args: argparse.Namespace) -> None:
    settings = AppSettings()  # type: ignore[call-arg]
    database = Database(
        settings.database_url.get_secret_value(),
        pool_size=1,
        max_overflow=0,
    )
    try:
        async with database.session_factory() as session, session.begin():
            await acquire_advisory_lock(session, namespace="plan-name", entity_id=args.name)
            plan = await session.scalar(
                select(Plan).where(Plan.name == args.name).with_for_update()
            )
            if plan is None:
                plan = Plan(name=args.name)
                session.add(plan)
            plan.duration_days = args.duration_days
            plan.price = args.price
            plan.currency = args.currency.upper()
            plan.traffic_limit_bytes = args.traffic_limit_bytes
            plan.device_limit = args.device_limit
            plan.sort_order = args.sort_order
            plan.is_active = not args.inactive
            await session.flush()
            print(f"Plan configured: id={plan.id}, name={plan.name}, active={plan.is_active}")
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--duration-days", required=True, type=int)
    parser.add_argument("--price", required=True, type=Decimal)
    parser.add_argument("--currency", default="RUB")
    parser.add_argument("--traffic-limit-bytes", type=int)
    parser.add_argument("--device-limit", type=int, default=1)
    parser.add_argument("--sort-order", type=int, default=0)
    parser.add_argument("--inactive", action="store_true")
    args = parser.parse_args()
    if args.duration_days <= 0 or args.price < 0 or args.device_limit <= 0:
        parser.error("duration-days and device-limit must be positive; price cannot be negative")
    if not args.name.strip() or len(args.currency) != 3:
        parser.error("name cannot be blank and currency must contain exactly 3 characters")
    asyncio.run(upsert_plan(args))


if __name__ == "__main__":
    main()
