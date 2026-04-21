from typing import Any

from pydantic import BaseModel, EmailStr


class ProfileUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    preferences: dict[str, Any] | None = None


class MoodCheckin(BaseModel):
    mood: str  # energetic | focused | good | tired | stressed


class ProfileRead(BaseModel):
    id: str
    name: str
    timezone: str
    mood_today: str | None
    preferences: dict[str, Any]
    created_at: str


# ── Auth request / response schemas ──────────────────────────────────────────

class AuthRegister(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class AuthLogin(BaseModel):
    email: EmailStr
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
