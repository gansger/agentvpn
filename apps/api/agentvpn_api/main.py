"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from apps.api.agentvpn_api.auth.sessions import SessionStore
from apps.api.agentvpn_api.config import AppSettings
from apps.api.agentvpn_api.database.session import Database
from apps.api.agentvpn_api.logging import configure_logging
from apps.api.agentvpn_api.payments.mock import MockPaymentProvider
from apps.api.agentvpn_api.payments.robokassa import RobokassaPaymentProvider
from apps.api.agentvpn_api.routers import auth, health, payments, plans, subscriptions
from apps.api.agentvpn_api.security import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    settings = AppSettings()  # type: ignore[call-arg]
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(
            settings.database_url.get_secret_value(),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
        redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            decode_responses=True,
        )
        app.state.settings = settings
        app.state.database = database
        app.state.redis = redis
        app.state.session_store = SessionStore(
            redis,
            session_secret=settings.session_secret.get_secret_value(),
            csrf_secret=settings.csrf_secret.get_secret_value(),
            session_ttl_seconds=settings.session_ttl_seconds,
            replay_ttl_seconds=settings.telegram_replay_ttl_seconds,
        )
        app.state.mock_payment_provider = MockPaymentProvider()
        robokassa_client: httpx.AsyncClient | None = None
        app.state.robokassa_payment_provider = None
        if settings.enable_robokassa_payments:
            merchant_login = settings.robokassa_merchant_login
            password_1 = settings.robokassa_password_1
            password_2 = settings.robokassa_password_2
            if merchant_login is None or password_1 is None or password_2 is None:
                raise RuntimeError("Robokassa settings validation failed")
            robokassa_client = httpx.AsyncClient(
                base_url=str(settings.robokassa_api_base_url).rstrip("/"),
                timeout=httpx.Timeout(10.0),
                follow_redirects=False,
            )
            app.state.robokassa_payment_provider = RobokassaPaymentProvider(
                client=robokassa_client,
                payment_url=str(settings.robokassa_payment_url),
                merchant_login=merchant_login,
                password_1=password_1.get_secret_value(),
                password_2=password_2.get_secret_value(),
                hash_algorithm=settings.robokassa_hash_algorithm,
                sbp_method=settings.robokassa_sbp_method,
                test_mode=settings.robokassa_test_mode,
            )
        yield
        if robokassa_client is not None:
            await robokassa_client.aclose()
        await redis.aclose()
        await database.dispose()

    app = FastAPI(
        title="AGentVPN API",
        version="0.4.0",
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(plans.router)
    app.include_router(payments.router)
    app.include_router(subscriptions.router)
    return app
