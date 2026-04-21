from typing import Any

from fastapi import APIRouter, Query, Request

from app.middleware.auth import get_user_id
from app.schemas.common import MessageResponse
from app.schemas.memory import MemoryCreate, MemoryRead, MemorySearchRequest, MemorySearchResult
from app.services import memory as mem_svc

router = APIRouter()


@router.get("", response_model=list[MemoryRead])
async def list_memories(
    request: Request,
    category: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> Any:
    user_id = get_user_id(request)
    return await mem_svc.list_memories(user_id, category=category, limit=limit)


@router.post("", response_model=MemoryRead, status_code=201)
async def create_memory(request: Request, body: MemoryCreate) -> Any:
    user_id = get_user_id(request)
    return await mem_svc.store(user_id, body.content, body.category, source="user_explicit")


@router.post("/search", response_model=list[MemorySearchResult])
async def search_memories(request: Request, body: MemorySearchRequest) -> Any:
    user_id = get_user_id(request)
    return await mem_svc.search(user_id, body.query, limit=body.limit)


@router.delete("/{memory_id}", response_model=MessageResponse)
async def delete_memory(request: Request, memory_id: str) -> Any:
    user_id = get_user_id(request)
    await mem_svc.delete(user_id, memory_id)
    return {"message": "Memory deleted"}
