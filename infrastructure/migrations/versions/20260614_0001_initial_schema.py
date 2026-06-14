"""Initial central source-of-truth schema.

Revision ID: 20260614_0001
Revises:
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260614_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_status = sa.Enum("active", "blocked", name="user_status")
subscription_status = sa.Enum(
    "pending", "active", "expired", "disabled", name="subscription_status"
)
provisioning_status = sa.Enum(
    "pending",
    "in_progress",
    "active",
    "partial_failed",
    "retrying",
    "manual_review",
    "disabled",
    name="provisioning_status",
)
payment_status = sa.Enum(
    "created", "waiting", "success", "failed", "expired", "refunded", name="payment_status"
)
vpn_protocol = sa.Enum("HYSTERIA2", "VLESS_REALITY", name="vpn_protocol")
binding_protocol = sa.Enum("HYSTERIA2", "VLESS_REALITY", name="binding_protocol")
binding_status = sa.Enum("pending", "active", "disabled", "error", "deleted", name="binding_status")
token_status = sa.Enum("active", "revoked", "expired", name="token_status")
webhook_status = sa.Enum(
    "received", "processed", "ignored", "failed", name="webhook_processing_status"
)
actor_type = sa.Enum("user", "admin", "system", "webhook", name="actor_type")


def timestamps() -> tuple[sa.Column[Any], sa.Column[Any]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(255)),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("language_code", sa.String(16)),
        sa.Column("status", user_status, server_default="active", nullable=False),
        sa.Column("referral_code", sa.String(64), unique=True),
        sa.Column("referred_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *timestamps(),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="RUB", nullable=False),
        sa.Column("traffic_limit_bytes", sa.BigInteger()),
        sa.Column("device_limit", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *timestamps(),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", subscription_status, server_default="pending", nullable=False),
        sa.Column(
            "provisioning_status", provisioning_status, server_default="pending", nullable=False
        ),
        sa.Column("auto_renew", sa.Boolean(), server_default=sa.false(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"])
    op.create_index("ix_subscriptions_expires_at", "subscriptions", ["expires_at"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="SET NULL")
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_invoice_id", sa.String(255)),
        sa.Column("order_id", sa.String(255), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", payment_status, server_default="created", nullable=False),
        sa.Column("payment_url", sa.Text()),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("expired_at", sa.DateTime(timezone=True)),
        sa.Column("refunded_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_payments_user_created_at", "payments", ["user_id", "created_at"])
    op.create_index("ix_payments_status_created_at", "payments", ["status", "created_at"])

    op.create_table(
        "vpn_servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("country_name", sa.String(128), nullable=False),
        sa.Column("city", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "vpn_inbounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "server_id",
            sa.Integer(),
            sa.ForeignKey("vpn_servers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_inbound_id", sa.Integer(), nullable=False),
        sa.Column("protocol", vpn_protocol, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint(
            "server_id",
            "external_inbound_id",
            name="uq_vpn_inbounds_server_external_id",
        ),
        sa.UniqueConstraint(
            "server_id",
            "protocol",
            name="uq_vpn_inbounds_server_protocol",
        ),
    )
    op.create_table(
        "xui_client_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inbound_id",
            sa.Integer(),
            sa.ForeignKey("vpn_inbounds.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("protocol", binding_protocol, nullable=False),
        sa.Column("external_client_id", sa.String(255), nullable=False, unique=True),
        sa.Column("external_email", sa.String(255), nullable=False, unique=True),
        sa.Column("external_sub_id", sa.String(255)),
        sa.Column("status", binding_status, server_default="pending", nullable=False),
        sa.Column("expiry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("traffic_limit_bytes", sa.BigInteger()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(128)),
        sa.Column("last_error_message", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "subscription_id",
            "protocol",
            name="uq_xui_bindings_subscription_protocol",
        ),
    )
    op.create_index(
        "ix_xui_bindings_status_last_synced",
        "xui_client_bindings",
        ["status", "last_synced_at"],
    )

    op.create_table(
        "happ_subscription_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(16), nullable=False),
        sa.Column("status", token_status, server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("rotated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_happ_subscription_tokens_token_prefix", "happ_subscription_tokens", ["token_prefix"]
    )
    op.create_index(
        "ix_happ_tokens_subscription_status",
        "happ_subscription_tokens",
        ["subscription_id", "status"],
    )

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_event_key", sa.String(255), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("processing_status", webhook_status, server_default="received", nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.String(500)),
        sa.UniqueConstraint(
            "provider",
            "external_event_key",
            name="uq_payment_webhook_provider_event",
        ),
    )
    op.create_index(
        "ix_webhook_events_status_received",
        "payment_webhook_events",
        ["processing_status", "received_at"],
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("actor_id", sa.String(255)),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(128), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_audit_entity_created", "audit_logs", ["entity_type", "entity_id", "created_at"]
    )


def downgrade() -> None:
    for table in (
        "audit_logs",
        "payment_webhook_events",
        "happ_subscription_tokens",
        "xui_client_bindings",
        "vpn_inbounds",
        "vpn_servers",
        "payments",
        "subscriptions",
        "plans",
        "users",
    ):
        op.drop_table(table)

    bind = op.get_bind()
    for enum_type in (
        actor_type,
        webhook_status,
        token_status,
        binding_status,
        binding_protocol,
        vpn_protocol,
        payment_status,
        provisioning_status,
        subscription_status,
        user_status,
    ):
        enum_type.drop(bind, checkfirst=True)
