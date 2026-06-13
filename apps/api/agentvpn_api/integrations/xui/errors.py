"""Sanitized errors raised by the 3x-ui adapter."""

from __future__ import annotations


class XuiError(RuntimeError):
    """Base error that never includes credentials or complete provider payloads."""


class XuiConfigurationError(XuiError):
    """Invalid or incomplete 3x-ui configuration."""


class XuiUnavailableError(XuiError):
    """Panel is unavailable or the circuit breaker is open."""


class XuiAuthenticationError(XuiError):
    """Panel rejected configured authentication."""


class XuiApiError(XuiError):
    """Panel returned an unsuccessful API result."""


class XuiContractError(XuiError):
    """Panel response does not match the installed OpenAPI contract."""


class XuiInboundValidationError(XuiError):
    """Configured inbound is unavailable or has an unexpected protocol."""
