import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, NotFoundError
from app.db.session import get_db
from app.schemas.memory import (
    MemoryDeleteResponse,
    MemoryListResponse,
    MemoryRead,
    MemorySearchRequest,
    MemorySearchResult,
)
from app.services.memory_service import (
    delete_all_memories,
    get_user_memories,
    semantic_search,
    soft_delete_memory,
)

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> MemoryListResponse:
    memories = await get_user_memories(_uid(request), db, limit=limit)
    items = [MemoryRead.model_validate(m) for m in memories]
    category_counts: dict[str, int] = {}
    for m in items:
        category_counts[m.category] = category_counts.get(m.category, 0) + 1
    return MemoryListResponse(items=items, total=len(items), categories=category_counts)


@router.post("/search", response_model=list[MemorySearchResult])
async def search_memories(
    data: MemorySearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[MemorySearchResult]:
    results = await semantic_search(
        _uid(request), data.query, limit=data.limit, category=data.category, db=db
    )
    return [
        MemorySearchResult(
            id=str(r["id"]),
            content=r["payload"].get("content", ""),
            category=r["payload"].get("category", ""),
            score=round(r["score"], 3),
        )
        for r in results
    ]


@router.delete("/{memory_id}", response_model=MemoryDeleteResponse)
async def delete_memory_endpoint(
    memory_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MemoryDeleteResponse:
    deleted = await soft_delete_memory(memory_id, _uid(request), db)
    if not deleted:
        raise NotFoundError(f"Memory {memory_id} not found")
    return MemoryDeleteResponse(deleted=True, id=memory_id)


@router.delete("", status_code=200)
async def delete_all(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    count = await delete_all_memories(_uid(request), db)
    return {"deleted": count, "message": f"All {count} memories have been erased."}
