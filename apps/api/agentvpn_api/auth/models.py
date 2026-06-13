"""Telegram authentication and session models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TelegramUserData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    language_code: str | None = Field(default=None, max_length=16)
    is_premium: bool | None = None


class ValidatedInitData(BaseModel):
    auth_date: int
    query_id: str | None = None
    start_param: str | None = None
    user: TelegramUserData
    replay_digest: str


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16384)


class PublicUser(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str
    language_code: str | None
    status: str


class AuthResponse(BaseModel):
    user: PublicUser
    csrf_token: str


class SessionRecord(BaseModel):
    user_id: int
    telegram_id: int
    csrf_token: str
    created_at: int
