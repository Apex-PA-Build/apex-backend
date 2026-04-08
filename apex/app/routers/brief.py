from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.brief import DailyBrief, MoodCheckin
from app.services.brief_service import generate_daily_brief

router = APIRouter()


async def _get_user(request: Request, db: AsyncSession) -> User:
    user_id: str | None = getattr(request.state, "user_id", None)
    if not user_id:
        raise AuthError("Not authenticated")
    result = await db.execute(select(User).where(User.id == user_id))  # type: ignore[arg-type]
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return user


@router.post("/generate", response_model=DailyBrief)
async def generate_brief(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> DailyBrief:
    """Generate (or regenerate) today's morning brief for the authenticated user."""
    user = await _get_user(request, db)
    brief_data = await generate_daily_brief(user, db)
    return DailyBrief(**brief_data)


@router.post("/mood-checkin", status_code=204)
async def mood_checkin(
    data: MoodCheckin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Record the user's mood check-in for today. Used to adjust task prioritization."""
    user = await _get_user(request, db)
    prefs = dict(user.preferences or {})
    prefs["last_mood"] = data.mood
    if data.note:
        prefs["last_mood_note"] = data.note
    user.preferences = prefs
