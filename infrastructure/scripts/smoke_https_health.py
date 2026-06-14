"""Verify public HTTPS liveness and readiness endpoints after deployment."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any
from urllib.request import Request, urlopen

DOMAIN_PATTERN = re.compile(
    r"(?=^.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)
EXPECTED_RESPONSES = {
    "/health/live": {"status": "ok"},
    "/health/ready": {"status": "ready"},
}


def validate_domain(value: str) -> str:
    domain = value.strip()
    if not DOMAIN_PATTERN.fullmatch(domain):
        raise ValueError("PUBLIC_DOMAIN must be a domain without scheme, path, port, or spaces")
    return domain


def read_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "agentvpn-deploy-smoke/1.0"})  # noqa: S310
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        payload: object = json.loads(response.read())
    if not isinstance(payload, dict):
        raise ValueError(f"{url} returned a non-object JSON response")
    return payload


def check_https_health(domain: str, *, timeout_seconds: float = 15) -> None:
    validated_domain = validate_domain(domain)
    for path, expected in EXPECTED_RESPONSES.items():
        url = f"https://{validated_domain}{path}"
        actual = read_json(url, timeout_seconds=timeout_seconds)
        if actual != expected:
            raise RuntimeError(f"{url} returned unexpected response: {actual!r}")
        print(f"OK {url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default=os.getenv("PUBLIC_DOMAIN", ""))
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    try:
        check_https_health(args.domain, timeout_seconds=args.timeout)
    except Exception as exc:
        print(f"HTTPS health smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
