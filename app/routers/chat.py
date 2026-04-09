from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.exceptions import AuthError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import process_chat

router = APIRouter()

def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid

@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    data: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    reply = await process_chat(_uid(request), data.message, db)
    return ChatResponse(reply=reply)
