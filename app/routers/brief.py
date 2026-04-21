from typing import Any

from fastapi import APIRouter, Request

from app.middleware.auth import get_user_id
from app.schemas.brief import DailyBrief, MoodCheckin
from app.services import brief as brief_svc

router = APIRouter()


@router.post("/generate", response_model=DailyBrief)
async def generate_brief(request: Request) -> Any:
    user_id = get_user_id(request)
    return await brief_svc.generate(user_id)


@router.post("/mood")
async def mood_checkin(request: Request, body: MoodCheckin) -> dict[str, str]:
    user_id = get_user_id(request)
    await brief_svc.save_mood(user_id, body.mood)
    return {"message": f"Got it — you're feeling {body.mood}. I'll factor that into your day."}
