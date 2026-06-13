"""Central source-of-truth database models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PythonEnum
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.agentvpn_api.database.base import Base, TimestampMixin

JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


def enum_column[EnumType: PythonEnum](
    enum_class: type[EnumType],
    name: str,
) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"


class ProvisioningStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ACTIVE = "active"
    PARTIAL_FAILED = "partial_failed"
    RETRYING = "retrying"
    MANUAL_REVIEW = "manual_review"
    DISABLED = "disabled"


class PaymentStatus(StrEnum):
    CREATED = "created"
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class VpnProtocol(StrEnum):
    HYSTERIA2 = "HYSTERIA2"
    VLESS_REALITY = "VLESS_REALITY"


class BindingStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
    DELETED = "deleted"


class TokenStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class WebhookProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


class ActorType(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
    WEBHOOK = "webhook"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[UserStatus] = mapped_column(
        enum_column(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    referral_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    referred_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Plan(TimestampMixin, Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    duration_days: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="RUB", server_default="RUB")
    traffic_limit_bytes: Mapped[int | None] = mapped_column(BigInteger)
    device_limit: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_status", "user_id", "status"),
        Index("ix_subscriptions_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[SubscriptionStatus] = mapped_column(
        enum_column(SubscriptionStatus, "subscription_status"),
        default=SubscriptionStatus.PENDING,
        server_default=SubscriptionStatus.PENDING.value,
    )
    provisioning_status: Mapped[ProvisioningStatus] = mapped_column(
        enum_column(ProvisioningStatus, "provisioning_status"),
        default=ProvisioningStatus.PENDING,
        server_default=ProvisioningStatus.PENDING.value,
    )
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_user_created_at", "user_id", "created_at"),
        Index("ix_payments_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_invoice_id: Mapped[str | None] = mapped_column(String(255))
    order_id: Mapped[str] = mapped_column(String(255), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"),
        default=PaymentStatus.CREATED,
        server_default=PaymentStatus.CREATED.value,
    )
    payment_url: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VpnServer(Base):
    __tablename__ = "vpn_servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(2))
    country_name: Mapped[str] = mapped_column(String(128))
    city: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VpnInbound(TimestampMixin, Base):
    __tablename__ = "vpn_inbounds"
    __table_args__ = (
        UniqueConstraint("server_id", "external_inbound_id"),
        UniqueConstraint("server_id", "protocol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("vpn_servers.id", ondelete="RESTRICT"))
    external_inbound_id: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[VpnProtocol] = mapped_column(enum_column(VpnProtocol, "vpn_protocol"))
    display_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class XuiClientBinding(Base):
    __tablename__ = "xui_client_bindings"
    __table_args__ = (
        UniqueConstraint("subscription_id", "protocol"),
        UniqueConstraint("external_client_id"),
        UniqueConstraint("external_email"),
        Index("ix_xui_bindings_status_last_synced", "status", "last_synced_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="RESTRICT")
    )
    inbound_id: Mapped[int] = mapped_column(ForeignKey("vpn_inbounds.id", ondelete="RESTRICT"))
    protocol: Mapped[VpnProtocol] = mapped_column(enum_column(VpnProtocol, "binding_protocol"))
    external_client_id: Mapped[str] = mapped_column(String(255))
    external_email: Mapped[str] = mapped_column(String(255))
    external_sub_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[BindingStatus] = mapped_column(
        enum_column(BindingStatus, "binding_status"),
        default=BindingStatus.PENDING,
        server_default=BindingStatus.PENDING.value,
    )
    expiry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    traffic_limit_bytes: Mapped[int | None] = mapped_column(BigInteger)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HappSubscriptionToken(Base):
    __tablename__ = "happ_subscription_tokens"
    __table_args__ = (Index("ix_happ_tokens_subscription_status", "subscription_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="RESTRICT")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_prefix: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[TokenStatus] = mapped_column(
        enum_column(TokenStatus, "token_status"),
        default=TokenStatus.ACTIVE,
        server_default=TokenStatus.ACTIVE.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_key"),
        Index("ix_webhook_events_status_received", "processing_status", "received_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    external_event_key: Mapped[str] = mapped_column(String(255))
    payload_hash: Mapped[str] = mapped_column(String(64))
    signature_valid: Mapped[bool] = mapped_column(Boolean)
    processing_status: Mapped[WebhookProcessingStatus] = mapped_column(
        enum_column(WebhookProcessingStatus, "webhook_processing_status"),
        default=WebhookProcessingStatus.RECEIVED,
        server_default=WebhookProcessingStatus.RECEIVED.value,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(500))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity_created", "entity_type", "entity_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[ActorType] = mapped_column(enum_column(ActorType, "actor_type"))
    actor_id: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(255))
    entity_type: Mapped[str] = mapped_column(String(128))
    entity_id: Mapped[str] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON_VALUE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
