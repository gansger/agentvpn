"""Robokassa hosted checkout adapter restricted to SBP payments."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx

from apps.api.agentvpn_api.payments.models import (
    InvoiceRequest,
    ProviderInvoice,
    ProviderPaymentStatus,
)

MAX_RESPONSE_BYTES = 256 * 1024
MAX_INVOICE_ID = (1 << 63) - 1
SUPPORTED_HASH_ALGORITHMS = {"md5", "sha256", "sha512"}


class RobokassaPaymentProviderError(RuntimeError):
    """Sanitized Robokassa error that never contains credentials or response payloads."""


def payment_signature(
    *,
    merchant_login: str,
    out_sum: str,
    invoice_id: str,
    password: str,
    shp_params: dict[str, str],
    algorithm: str,
) -> str:
    parts = [merchant_login, out_sum, invoice_id, password]
    parts.extend(f"{key}={shp_params[key]}" for key in sorted(shp_params))
    return _digest(":".join(parts), algorithm)


def result_signature(
    *,
    out_sum: str,
    invoice_id: str,
    password: str,
    shp_params: dict[str, str],
    algorithm: str,
) -> str:
    parts = [out_sum, invoice_id, password]
    parts.extend(f"{key}={shp_params[key]}" for key in sorted(shp_params))
    return _digest(":".join(parts), algorithm)


def _digest(value: str, algorithm: str) -> str:
    normalized = algorithm.lower()
    if normalized not in SUPPORTED_HASH_ALGORITHMS:
        raise RobokassaPaymentProviderError("Unsupported Robokassa hash algorithm")
    return hashlib.new(normalized, value.encode("utf-8")).hexdigest()


def _invoice_id(order_id: str) -> str:
    value = int.from_bytes(hashlib.sha256(order_id.encode("utf-8")).digest()[:8], "big")
    return str((value & MAX_INVOICE_ID) or 1)


def _amount(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


class RobokassaPaymentProvider:
    name = "robokassa"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        payment_url: str,
        merchant_login: str,
        password_1: str,
        password_2: str,
        hash_algorithm: str,
        sbp_method: str,
        test_mode: bool,
    ) -> None:
        self._client = client
        self._payment_url = payment_url
        self._merchant_login = merchant_login
        self._password_1 = password_1
        self._password_2 = password_2
        self._hash_algorithm = hash_algorithm.lower()
        self._sbp_method = sbp_method
        self._test_mode = test_mode
        if self._hash_algorithm not in SUPPORTED_HASH_ALGORITHMS:
            raise RobokassaPaymentProviderError("Unsupported Robokassa hash algorithm")

    async def create_invoice(self, request: InvoiceRequest) -> ProviderInvoice:
        if request.currency != "RUB":
            raise RobokassaPaymentProviderError("Robokassa SBP checkout requires RUB")
        invoice_id = _invoice_id(request.order_id)
        out_sum = _amount(request.amount)
        shp_params = {"Shp_order_id": request.order_id}
        signature = payment_signature(
            merchant_login=self._merchant_login,
            out_sum=out_sum,
            invoice_id=invoice_id,
            password=self._password_1,
            shp_params=shp_params,
            algorithm=self._hash_algorithm,
        )
        query = urlencode(
            {
                "MerchantLogin": self._merchant_login,
                "OutSum": out_sum,
                "InvId": invoice_id,
                "Description": request.description[:100],
                "SignatureValue": signature,
                "Culture": "ru",
                "Encoding": "utf-8",
                "IsTest": "1" if self._test_mode else "0",
                "PaymentMethods": self._sbp_method,
                **shp_params,
            }
        )
        return ProviderInvoice(
            provider_invoice_id=invoice_id,
            payment_url=f"{self._payment_url}?{query}",
            status=ProviderPaymentStatus.WAITING,
            sanitized_payload={
                "provider": self.name,
                "method": self._sbp_method,
                "test_mode": self._test_mode,
            },
        )

    async def get_invoice(self, provider_invoice_id: str) -> ProviderInvoice:
        if self._test_mode:
            return ProviderInvoice(
                provider_invoice_id=provider_invoice_id,
                payment_url=None,
                status=ProviderPaymentStatus.WAITING,
                sanitized_payload={"provider": self.name, "test_mode": True},
            )
        signature = _digest(
            f"{self._merchant_login}:{provider_invoice_id}:{self._password_2}",
            self._hash_algorithm,
        )
        root = await self._request_xml(
            "/Merchant/WebService/Service.asmx/OpStateExt",
            params={
                "MerchantLogin": self._merchant_login,
                "InvoiceID": provider_invoice_id,
                "Signature": signature,
            },
        )
        state_code = self._state_code(root)
        if state_code is None:
            raise RobokassaPaymentProviderError("Robokassa response is missing payment state")
        status = {
            "5": ProviderPaymentStatus.WAITING,
            "10": ProviderPaymentStatus.FAILED,
            "20": ProviderPaymentStatus.WAITING,
            "50": ProviderPaymentStatus.WAITING,
            "60": ProviderPaymentStatus.REFUNDED,
            "80": ProviderPaymentStatus.WAITING,
            "100": ProviderPaymentStatus.SUCCESS,
        }.get(state_code)
        if status is None:
            raise RobokassaPaymentProviderError("Robokassa returned an unknown payment state")
        return ProviderInvoice(
            provider_invoice_id=provider_invoice_id,
            payment_url=None,
            status=status,
            sanitized_payload={"provider": self.name, "state_code": state_code},
        )

    async def get_enabled_methods(self) -> set[str]:
        root = await self._request_xml(
            "/Merchant/WebService/Service.asmx/GetCurrencies",
            params={"MerchantLogin": self._merchant_login, "Language": "ru"},
        )
        return {
            alias
            for element in root.iter()
            if _local_name(element.tag) == "Currency"
            and isinstance((alias := element.attrib.get("Alias")), str)
            and alias
        }

    async def _request_xml(self, path: str, **kwargs: Any) -> ElementTree.Element:
        try:
            response = await self._client.get(path, **kwargs)
        except httpx.HTTPError as exc:
            raise RobokassaPaymentProviderError("Robokassa API request failed") from exc
        if not response.is_success:
            raise RobokassaPaymentProviderError("Robokassa API rejected the request")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise RobokassaPaymentProviderError("Robokassa API response exceeded the size limit")
        try:
            root = ElementTree.fromstring(response.content)  # noqa: S314
        except ElementTree.ParseError as exc:
            raise RobokassaPaymentProviderError("Robokassa API returned invalid XML") from exc
        if self._result_code(root) != "0":
            raise RobokassaPaymentProviderError("Robokassa API returned an unsuccessful result")
        return root

    @staticmethod
    def _result_code(root: ElementTree.Element) -> str | None:
        for element in root.iter():
            if _local_name(element.tag) == "Result":
                for child in element:
                    if _local_name(child.tag) == "Code":
                        return child.text
        return None

    @staticmethod
    def _state_code(root: ElementTree.Element) -> str | None:
        for element in root.iter():
            if _local_name(element.tag) == "State":
                for child in element:
                    if _local_name(child.tag) == "Code":
                        return child.text
        return None
