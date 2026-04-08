import base64
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def encode_cursor(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode()


def decode_cursor(cursor: str) -> str:
    try:
        return base64.urlsafe_b64decode(cursor.encode()).decode()
    except Exception:
        return ""


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    next_cursor: str | None = None
    has_more: bool


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None


def paginate(
    items: list[Any],
    total: int,
    limit: int,
    cursor_field: str = "created_at",
) -> dict[str, Any]:
    has_more = len(items) == limit
    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        raw_val = getattr(last, cursor_field, None)
        if isinstance(raw_val, datetime):
            raw_val = raw_val.isoformat()
        if raw_val is not None:
            next_cursor = encode_cursor(str(raw_val))

    return {
        "items": items,
        "total": total,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
