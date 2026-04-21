from pydantic import BaseModel


class MemoryRead(BaseModel):
    id: str
    content: str
    category: str
    source: str
    created_at: str


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10


class MemorySearchResult(BaseModel):
    id: str
    content: str
    category: str
    source: str
    similarity: float
    created_at: str


class MemoryCreate(BaseModel):
    content: str
    category: str  # preference | relationship | pattern | fact | decision | commitment
