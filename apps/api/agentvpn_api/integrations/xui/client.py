"""Async HTTP client for the installed 3x-ui OpenAPI contract."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from apps.api.agentvpn_api.integrations.xui.errors import (
    XuiApiError,
    XuiAuthenticationError,
    XuiContractError,
    XuiUnavailableError,
)
from apps.api.agentvpn_api.integrations.xui.models import (
    ApiEnvelope,
    XuiClientCreate,
    XuiClientRecord,
    XuiClientTraffic,
    XuiInbound,
    XuiServerStatus,
)
from apps.api.agentvpn_api.integrations.xui.settings import XuiSettings

RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})
QueryValue = str | int | float | bool | None


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_seconds: float) -> None:
        self._failure_threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def ensure_available(self) -> None:
        if self._opened_at is None:
            return
        if time.monotonic() - self._opened_at >= self._reset_seconds:
            self._opened_at = None
            self._failures = 0
            return
        raise XuiUnavailableError("3x-ui circuit breaker is open")

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._opened_at = time.monotonic()


class ThreeXUIApiClient:
    def __init__(
        self,
        settings: XuiSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.normalized_base_url,
            timeout=settings.request_timeout_seconds,
            verify=settings.verify_tls,
            follow_redirects=False,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": "agentvpn-api/0.1"},
        )
        self._breaker = CircuitBreaker(
            settings.circuit_failure_threshold,
            settings.circuit_reset_seconds,
        )
        self._session_authenticated = False
        self._auth_lock = asyncio.Lock()

    async def __aenter__(self) -> ThreeXUIApiClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    def _bearer_headers(self) -> dict[str, str]:
        if self._settings.api_token is None or self._session_authenticated:
            return {}
        return {"Authorization": f"Bearer {self._settings.api_token.get_secret_value()}"}

    async def _login(self) -> None:
        if self._settings.username is None or self._settings.password is None:
            raise XuiAuthenticationError("3x-ui rejected the configured API token")

        async with self._auth_lock:
            if self._session_authenticated:
                return
            payload = {
                "username": self._settings.username,
                "password": self._settings.password.get_secret_value(),
                "twoFactorCode": (
                    self._settings.two_factor_code.get_secret_value()
                    if self._settings.two_factor_code is not None
                    else ""
                ),
            }
            try:
                response = await self._client.post("login", json=payload)
            except httpx.TransportError as exc:
                raise XuiUnavailableError("Unable to reach 3x-ui login endpoint") from exc
            envelope = self._parse_envelope(response)
            if response.status_code != 200 or not envelope.success:
                raise XuiAuthenticationError("3x-ui session authentication failed")
            self._session_authenticated = True

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, object] | None = None,
        params: Mapping[str, QueryValue] | None = None,
        safe_to_retry: bool,
        allow_unsuccessful: bool = False,
    ) -> ApiEnvelope[Any]:
        self._breaker.ensure_available()
        attempts = self._settings.safe_retry_attempts if safe_to_retry else 1
        authenticated_once = False
        attempt = 0

        while attempt < attempts:
            try:
                response = await self._client.request(
                    method,
                    path.lstrip("/"),
                    json=json_body,
                    params=params,
                    headers=self._bearer_headers(),
                )
            except httpx.TransportError as exc:
                self._breaker.record_failure()
                attempt += 1
                if attempt < attempts:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                raise XuiUnavailableError("3x-ui request failed") from exc

            if response.status_code in {401, 403} and not authenticated_once:
                authenticated_once = True
                self._session_authenticated = False
                await self._login()
                continue
            if response.status_code in RETRYABLE_STATUS_CODES:
                self._breaker.record_failure()
                attempt += 1
                if attempt < attempts:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                raise XuiUnavailableError("3x-ui returned a temporary server error")
            if response.status_code >= 400:
                self._breaker.record_failure()
                raise XuiApiError(f"3x-ui returned HTTP {response.status_code}")

            envelope = self._parse_envelope(response)
            if not envelope.success and not allow_unsuccessful:
                raise XuiApiError(self._safe_message(envelope.msg))
            self._breaker.record_success()
            return envelope

        raise XuiUnavailableError("3x-ui safe retry attempts exhausted")

    @staticmethod
    def _parse_envelope(response: httpx.Response) -> ApiEnvelope[Any]:
        try:
            return ApiEnvelope[Any].model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise XuiContractError("3x-ui returned an invalid API response") from exc

    @staticmethod
    def _safe_message(message: str | None) -> str:
        if not message:
            return "3x-ui operation was unsuccessful"
        sanitized = " ".join(message.split())
        return sanitized[:200]

    async def health_check(self) -> XuiServerStatus:
        envelope = await self._request("GET", "/panel/api/server/status", safe_to_retry=True)
        return XuiServerStatus.model_validate(envelope.obj)

    async def get_inbound(self, inbound_id: int) -> XuiInbound:
        envelope = await self._request(
            "GET", f"/panel/api/inbounds/get/{inbound_id}", safe_to_retry=True
        )
        return XuiInbound.model_validate(envelope.obj)

    async def create_client(self, client: XuiClientCreate, inbound_ids: list[int]) -> None:
        await self._request(
            "POST",
            "/panel/api/clients/add",
            json_body={
                "client": client.model_dump(by_alias=True, exclude_none=True),
                "inboundIds": inbound_ids,
            },
            safe_to_retry=False,
        )

    async def update_client(self, email: str, full_payload: Mapping[str, object]) -> None:
        await self._request(
            "POST",
            f"/panel/api/clients/update/{quote(email, safe='')}",
            json_body=full_payload,
            safe_to_retry=False,
        )

    async def attach_client(self, email: str, inbound_ids: list[int]) -> None:
        await self._request(
            "POST",
            f"/panel/api/clients/{quote(email, safe='')}/attach",
            json_body={"inboundIds": inbound_ids},
            safe_to_retry=False,
        )

    async def delete_client(self, email: str, *, keep_traffic: bool = True) -> None:
        await self._request(
            "POST",
            f"/panel/api/clients/del/{quote(email, safe='')}",
            params={"keepTraffic": 1 if keep_traffic else 0},
            safe_to_retry=False,
        )

    async def get_client(self, email: str) -> XuiClientRecord | None:
        envelope = await self._request(
            "GET",
            f"/panel/api/clients/get/{quote(email, safe='')}",
            safe_to_retry=True,
            allow_unsuccessful=True,
        )
        if not envelope.success or envelope.obj is None:
            message = self._safe_message(envelope.msg).lower()
            if "not found" in message or "does not exist" in message:
                return None
            raise XuiApiError(self._safe_message(envelope.msg))
        return XuiClientRecord.model_validate(envelope.obj)

    async def get_client_traffic(self, email: str) -> XuiClientTraffic:
        envelope = await self._request(
            "GET",
            f"/panel/api/clients/traffic/{quote(email, safe='')}",
            safe_to_retry=True,
        )
        return XuiClientTraffic.model_validate(envelope.obj)

    async def get_client_links(self, email: str) -> list[str]:
        envelope = await self._request(
            "GET",
            f"/panel/api/clients/links/{quote(email, safe='')}",
            safe_to_retry=True,
        )
        if not isinstance(envelope.obj, list) or not all(
            isinstance(link, str) for link in envelope.obj
        ):
            raise XuiContractError("3x-ui client links response has an invalid shape")
        return envelope.obj

    async def list_online_clients(self) -> list[str]:
        envelope = await self._request("POST", "/panel/api/clients/onlines", safe_to_retry=True)
        if not isinstance(envelope.obj, list) or not all(
            isinstance(email, str) for email in envelope.obj
        ):
            raise XuiContractError("3x-ui online clients response has an invalid shape")
        return envelope.obj
