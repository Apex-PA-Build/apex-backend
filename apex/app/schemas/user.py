import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    timezone: str = Field(default="UTC", max_length=64)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    name: str
    timezone: str
    preferences: dict[str, Any]
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    preferences: dict[str, Any] | None = None


class UserPreferences(BaseModel):
    """Typed subset of the preferences JSON blob."""
    work_start_hour: int = Field(default=9, ge=0, le=23)
    work_end_hour: int = Field(default=18, ge=0, le=23)
    focus_block_duration_minutes: int = Field(default=90, ge=15, le=240)
    default_buffer_minutes: int = Field(default=10, ge=0, le=60)
    energy_peak: str = Field(default="morning")  # morning | afternoon | evening
    notification_style: str = Field(default="normal")  # minimal | normal | proactive


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
