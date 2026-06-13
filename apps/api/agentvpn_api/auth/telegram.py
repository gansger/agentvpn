"""Server-side Telegram Mini App initData verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from pydantic import ValidationError

from apps.api.agentvpn_api.auth.models import TelegramUserData, ValidatedInitData


class TelegramInitDataError(ValueError):
    """Raised for invalid, expired, or malformed Telegram initData."""


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int,
    now: int | None = None,
) -> ValidatedInitData:
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise TelegramInitDataError("Telegram initData is malformed") from exc

    fields = dict(pairs)
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise TelegramInitDataError("Telegram initData hash is missing")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramInitDataError("Telegram initData signature is invalid")

    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError) as exc:
        raise TelegramInitDataError("Telegram initData auth_date is invalid") from exc

    current_time = int(time.time()) if now is None else now
    if auth_date > current_time + 30:
        raise TelegramInitDataError("Telegram initData auth_date is in the future")
    if current_time - auth_date > max_age_seconds:
        raise TelegramInitDataError("Telegram initData has expired")

    try:
        raw_user: object = json.loads(fields["user"])
        user = TelegramUserData.model_validate(raw_user)
    except (KeyError, json.JSONDecodeError, ValidationError) as exc:
        raise TelegramInitDataError("Telegram initData user is invalid") from exc

    replay_digest = hashlib.sha256(init_data.encode()).hexdigest()
    return ValidatedInitData(
        auth_date=auth_date,
        query_id=fields.get("query_id"),
        start_param=fields.get("start_param"),
        user=user,
        replay_digest=replay_digest,
    )
