"""Fetch the OpenAPI schema from the installed 3x-ui panel without leaking credentials."""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import tempfile
from email.message import Message
from pathlib import Path
from typing import Final, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

MAX_SCHEMA_BYTES: Final = 10 * 1024 * 1024
DEFAULT_OPENAPI_PATH: Final = "/panel/api/openapi.json"
OUTPUT_PATH: Final = Path(__file__).resolve().parents[2] / "docs" / "3x-ui-openapi.json"


class ReadableResponse(Protocol):
    headers: Message

    def read(self, amt: int = -1) -> bytes: ...


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    if parts.port:
        hostname = f"{hostname}:{parts.port}"
    return urlunsplit((parts.scheme, hostname, parts.path, "", ""))


def build_schema_url(base_url: str, openapi_path: str) -> str:
    return f"{base_url.rstrip('/')}/{openapi_path.lstrip('/')}"


def validate_transport(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme == "https":
        return
    if parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost", "::1"}:
        return
    raise ValueError("XUI_BASE_URL must use HTTPS unless it points to a local development host")


def build_request(url: str) -> Request:
    headers = {"Accept": "application/json", "User-Agent": "agentvpn-openapi-snapshot/1"}
    token = os.getenv("XUI_API_TOKEN", "").strip()
    if token:
        header_name = os.getenv("XUI_API_TOKEN_HEADER", "Authorization").strip()
        scheme = os.getenv("XUI_API_TOKEN_SCHEME", "Bearer").strip()
        headers[header_name] = f"{scheme} {token}".strip()
    # URL policy is enforced by validate_transport before this request is opened.
    return Request(url, headers=headers, method="GET")  # noqa: S310


def read_limited(response: ReadableResponse) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_SCHEMA_BYTES:
        raise ValueError("OpenAPI response is larger than the configured safety limit")
    payload = response.read(MAX_SCHEMA_BYTES + 1)
    if len(payload) > MAX_SCHEMA_BYTES:
        raise ValueError("OpenAPI response exceeded the configured safety limit")
    return payload


def validate_schema(payload: bytes) -> dict[str, object]:
    raw_document: object = json.loads(payload)
    if not isinstance(raw_document, dict):
        raise ValueError("OpenAPI document must be a JSON object")
    document = cast(dict[str, object], raw_document)
    version = document.get("openapi") or document.get("swagger")
    paths = document.get("paths")
    if not isinstance(version, str) or not isinstance(paths, dict):
        raise ValueError("Response is not a usable OpenAPI document")
    return document


def write_atomically(document: dict[str, object]) -> str:
    serialized = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    digest = hashlib.sha256(serialized).hexdigest()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=OUTPUT_PATH.parent, prefix=".3x-ui-openapi-", delete=False
    ) as temporary:
        temporary.write(serialized)
        temporary.flush()
        temp_path = Path(temporary.name)
    temp_path.replace(OUTPUT_PATH)
    return digest


def main() -> int:
    base_url = os.getenv("XUI_BASE_URL", "").strip()
    if not base_url:
        print("XUI_BASE_URL is required", file=sys.stderr)
        return 2

    openapi_path = os.getenv("XUI_OPENAPI_PATH", DEFAULT_OPENAPI_PATH).strip()
    schema_url = build_schema_url(base_url, openapi_path)

    try:
        validate_transport(schema_url)
        verify_tls = env_bool("XUI_VERIFY_TLS", True)
        context = ssl.create_default_context()
        if not verify_tls:
            hostname = urlsplit(schema_url).hostname
            if hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("XUI_VERIFY_TLS=false is allowed only for local discovery")
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        timeout = float(os.getenv("XUI_REQUEST_TIMEOUT_SECONDS", "10"))
        # URL scheme and TLS policy were validated above.
        with urlopen(  # noqa: S310
            build_request(schema_url), timeout=timeout, context=context
        ) as response:
            document = validate_schema(read_limited(response))
        digest = write_atomically(document)
    except HTTPError as exc:
        print(
            f"3x-ui returned HTTP {exc.code} for {redact_url(schema_url)}. "
            "Confirm the installed panel authentication method.",
            file=sys.stderr,
        )
        return 1
    except (URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Unable to fetch {redact_url(schema_url)}: {exc}", file=sys.stderr)
        return 1

    print(f"Saved {OUTPUT_PATH} (sha256={digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
