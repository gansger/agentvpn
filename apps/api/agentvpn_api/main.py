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
from apps.api.agentvpn_api.payments.enot import EnotPaymentProvider
from apps.api.agentvpn_api.payments.mock import MockPaymentProvider
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
        enot_client: httpx.AsyncClient | None = None
        app.state.enot_payment_provider = None
        if settings.enable_enot_payments:
            shop_id = settings.enot_shop_id
            secret_key = settings.enot_secret_key
            if shop_id is None or secret_key is None:
                raise RuntimeError("ENOT settings validation failed")
            enot_client = httpx.AsyncClient(
                base_url=str(settings.enot_api_base_url).rstrip("/"),
                timeout=httpx.Timeout(10.0),
                follow_redirects=False,
            )
            app.state.enot_payment_provider = EnotPaymentProvider(
                client=enot_client,
                shop_id=shop_id,
                secret_key=secret_key.get_secret_value(),
                webhook_url=settings.enot_webhook_url,
                success_url=settings.public_origin,
                fail_url=settings.public_origin,
                service_code=settings.enot_sbp_service_code,
                expire_minutes=settings.enot_payment_expire_minutes,
            )
        yield
        if enot_client is not None:
            await enot_client.aclose()
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
