"""HTTP security helpers and middleware."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.agentvpn_api.auth.models import SessionRecord
from apps.api.agentvpn_api.auth.sessions import SessionStore
from apps.api.agentvpn_api.config import AppSettings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors https://web.telegram.org "
            "https://*.telegram.org; object-src 'none'; base-uri 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


def get_settings(request: Request) -> AppSettings:
    return cast(AppSettings, request.app.state.settings)


def get_session_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.session_store)


async def require_session(request: Request) -> SessionRecord:
    settings = get_settings(request)
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    session = await get_session_store(request).get(token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    request.state.session_token = token
    return session


async def require_csrf(request: Request, session: SessionRecord) -> None:
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
