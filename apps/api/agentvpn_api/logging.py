"""Minimal structured JSON logging with secret-field redaction."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

REDACTED_FIELDS = frozenset(
    {
        "authorization",
        "cookie",
        "csrf_token",
        "init_data",
        "password",
        "secret",
        "session",
        "token",
    }
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = getattr(record, "event_data", None)
        if isinstance(extras, dict):
            payload["data"] = {
                key: "[REDACTED]" if key.lower() in REDACTED_FIELDS else value
                for key, value in extras.items()
            }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
