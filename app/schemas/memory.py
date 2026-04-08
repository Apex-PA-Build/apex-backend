import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MemoryRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    content: str
    category: str
    source: str
    created_at: datetime


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    category: str | None = None


class MemorySearchResult(BaseModel):
    id: str
    content: str
    category: str
    score: float
    created_at: datetime | None = None


class MemoryDeleteResponse(BaseModel):
    deleted: bool
    id: uuid.UUID


class MemoryListResponse(BaseModel):
    items: list[MemoryRead]
    total: int
    categories: dict[str, int]  # category -> count
