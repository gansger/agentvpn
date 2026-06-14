"""Add payment and plan integrity constraints.

Revision ID: 20260614_0002
Revises: 20260614_0001
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_0002"
down_revision: str | None = "20260614_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_plans_name", "plans", ["name"])
    op.create_check_constraint("ck_plans_duration_positive", "plans", "duration_days > 0")
    op.create_check_constraint("ck_plans_price_nonnegative", "plans", "price >= 0")
    op.create_check_constraint("ck_plans_currency_length", "plans", "char_length(currency) = 3")
    op.create_check_constraint("ck_plans_device_limit_positive", "plans", "device_limit > 0")
    op.create_check_constraint("ck_payments_amount_nonnegative", "payments", "amount >= 0")
    op.create_check_constraint(
        "ck_payments_currency_length",
        "payments",
        "char_length(currency) = 3",
    )
    op.create_unique_constraint(
        "uq_payments_provider_invoice",
        "payments",
        ["provider", "provider_invoice_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_payments_provider_invoice", "payments", type_="unique")
    op.drop_constraint("ck_payments_currency_length", "payments", type_="check")
    op.drop_constraint("ck_payments_amount_nonnegative", "payments", type_="check")
    op.drop_constraint("ck_plans_device_limit_positive", "plans", type_="check")
    op.drop_constraint("ck_plans_currency_length", "plans", type_="check")
    op.drop_constraint("ck_plans_price_nonnegative", "plans", type_="check")
    op.drop_constraint("ck_plans_duration_positive", "plans", type_="check")
    op.drop_constraint("uq_plans_name", "plans", type_="unique")
