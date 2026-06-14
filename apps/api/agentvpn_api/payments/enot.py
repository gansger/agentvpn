"""ENOT payment provider adapter for hosted SBP checkout."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from apps.api.agentvpn_api.payments.models import (
    InvoiceRequest,
    ProviderInvoice,
    ProviderPaymentStatus,
)

MAX_RESPONSE_BYTES = 256 * 1024


class EnotPaymentProviderError(RuntimeError):
    """Sanitized ENOT API error that never contains credentials or response payloads."""


def provider_status(value: object) -> ProviderPaymentStatus:
    mapping = {
        "created": ProviderPaymentStatus.WAITING,
        "success": ProviderPaymentStatus.SUCCESS,
        "fail": ProviderPaymentStatus.FAILED,
        "expired": ProviderPaymentStatus.EXPIRED,
        "refund": ProviderPaymentStatus.REFUNDED,
    }
    try:
        return mapping[str(value)]
    except KeyError as exc:
        raise EnotPaymentProviderError("ENOT returned an unknown payment status") from exc


def json_amount(amount: Decimal) -> int | float:
    integral = amount.to_integral_value()
    return int(integral) if amount == integral else float(amount)


class EnotPaymentProvider:
    name = "enot"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        shop_id: str,
        secret_key: str,
        webhook_url: str,
        success_url: str,
        fail_url: str,
        service_code: str,
        expire_minutes: int,
    ) -> None:
        self._client = client
        self._shop_id = shop_id
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": secret_key,
        }
        self._webhook_url = webhook_url
        self._success_url = success_url
        self._fail_url = fail_url
        self._service_code = service_code
        self._expire_minutes = expire_minutes

    async def create_invoice(self, request: InvoiceRequest) -> ProviderInvoice:
        payload = {
            "amount": json_amount(request.amount),
            "order_id": request.order_id,
            "currency": request.currency,
            "shop_id": self._shop_id,
            "hook_url": self._webhook_url,
            "success_url": self._success_url,
            "fail_url": self._fail_url,
            "comment": request.description,
            "expire": self._expire_minutes,
            "include_service": [self._service_code],
            "custom_fields": json.dumps(
                {"order_id": request.order_id},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        data = await self._request("POST", "/invoice/create", json=payload)
        invoice_id = self._required_string(data, "id")
        payment_url = self._required_string(data, "url")
        currency = self._required_string(data, "currency")
        if currency != request.currency or self._decimal(data.get("amount")) != request.amount:
            raise EnotPaymentProviderError("ENOT invoice does not match the requested payment")
        return ProviderInvoice(
            provider_invoice_id=invoice_id,
            payment_url=payment_url,
            status=ProviderPaymentStatus.WAITING,
            sanitized_payload={
                "provider": self.name,
                "service": self._service_code,
                "expired": data.get("expired"),
            },
        )

    async def get_invoice(self, provider_invoice_id: str) -> ProviderInvoice:
        data = await self._request(
            "GET",
            "/invoice/info",
            params={"invoice_id": provider_invoice_id, "shop_id": self._shop_id},
        )
        invoice_id = self._required_string(data, "invoice_id")
        if invoice_id != provider_invoice_id:
            raise EnotPaymentProviderError("ENOT returned a mismatched invoice")
        return ProviderInvoice(
            provider_invoice_id=invoice_id,
            payment_url=None,
            status=provider_status(data.get("status")),
            sanitized_payload={
                "provider": self.name,
                "service": data.get("pay_service"),
            },
        )

    async def get_enabled_services(self, *, currency: str = "RUB") -> set[str]:
        data = await self._request("GET", f"/shops/{self._shop_id}/payment-tariffs")
        tariffs = data.get("tariffs")
        if not isinstance(tariffs, list):
            raise EnotPaymentProviderError("ENOT response is missing payment tariffs")
        return {
            service
            for tariff in tariffs
            if isinstance(tariff, dict)
            and tariff.get("status") == "enabled"
            and tariff.get("currency") == currency
            and isinstance((service := tariff.get("service")), str)
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise EnotPaymentProviderError("ENOT API request failed") from exc
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise EnotPaymentProviderError("ENOT API response exceeded the size limit")
        try:
            payload = response.json()
        except ValueError as exc:
            raise EnotPaymentProviderError("ENOT API returned invalid JSON") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if (
            not response.is_success
            or not isinstance(payload, dict)
            or payload.get("status_check") is not True
            or not isinstance(data, dict)
        ):
            raise EnotPaymentProviderError("ENOT API rejected the request")
        return data

    @staticmethod
    def _required_string(data: dict[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise EnotPaymentProviderError(f"ENOT response is missing {key}")
        return value

    @staticmethod
    def _decimal(value: object) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise EnotPaymentProviderError("ENOT returned an invalid amount") from exc
