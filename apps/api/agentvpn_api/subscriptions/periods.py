"""Pure UTC subscription period calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class SubscriptionPeriod:
    starts_at: datetime
    expires_at: datetime


def calculate_subscription_period(
    *,
    now: datetime,
    duration_days: int,
    current_starts_at: datetime | None = None,
    current_expires_at: datetime | None = None,
) -> SubscriptionPeriod:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")
    if (current_starts_at is None) != (current_expires_at is None):
        raise ValueError("current period must contain both starts_at and expires_at")
    if current_starts_at is not None and current_starts_at.tzinfo is None:
        raise ValueError("current_starts_at must be timezone-aware")
    if current_expires_at is not None and current_expires_at.tzinfo is None:
        raise ValueError("current_expires_at must be timezone-aware")

    if (
        current_starts_at is not None
        and current_expires_at is not None
        and current_expires_at > now
    ):
        return SubscriptionPeriod(
            starts_at=current_starts_at,
            expires_at=current_expires_at + timedelta(days=duration_days),
        )
    return SubscriptionPeriod(starts_at=now, expires_at=now + timedelta(days=duration_days))
