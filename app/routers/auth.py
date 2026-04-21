from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.core.supabase import get_client
from app.middleware.auth import get_user_id
from app.schemas.user import (
    AuthLogin,
    AuthRegister,
    AuthTokenResponse,
    MoodCheckin,
    ProfileRead,
    ProfileUpdate,
)
from app.services import brief as brief_svc

router = APIRouter()


# ── Public: register & login ───────────────────────────────────────────────

@router.post("/register", response_model=AuthTokenResponse, summary="Register a new user")
async def register(body: AuthRegister) -> Any:
    """Create a new Supabase user and return a usable access token."""
    client = await get_client()
    try:
        res = await client.auth.sign_up(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if res.user is None:
        raise HTTPException(
            status_code=400,
            detail="Registration failed — check that email confirmation is disabled in Supabase or confirm the email first.",
        )

    session = res.session
    if session is None:
        raise HTTPException(
            status_code=400,
            detail="User created but no session returned. Email confirmation may be required.",
        )

    # Optionally set display name
    if body.name:
        await client.table("profiles").upsert(
            {"id": res.user.id, "name": body.name}
        ).execute()

    return AuthTokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in or 3600,
        user_id=str(res.user.id),
        email=res.user.email or body.email,
    )


@router.post("/login", response_model=AuthTokenResponse, summary="Login and get token")
async def login(body: AuthLogin) -> Any:
    """Sign in with email + password and return the access token."""
    client = await get_client()
    try:
        res = await client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc

    if res.session is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthTokenResponse(
        access_token=res.session.access_token,
        expires_in=res.session.expires_in or 3600,
        user_id=str(res.user.id),
        email=res.user.email or body.email,
    )


# ── Protected: profile & mood ───────────────────────────────────────────────

@router.get("/me", response_model=ProfileRead)
async def get_profile(request: Request) -> Any:
    user_id = get_user_id(request)
    client = await get_client()
    result = await client.table("profiles").select("*").eq("id", user_id).execute()
    if not result.data:
        # Auto-create profile if it doesn't exist (fallback for new users)
        result = await client.table("profiles").insert({"id": user_id, "name": "New User"}).execute()
    return result.data[0]


@router.patch("/me", response_model=ProfileRead)
async def update_profile(request: Request, body: ProfileUpdate) -> Any:
    user_id = get_user_id(request)
    client = await get_client()
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    result = await client.table("profiles").update(payload).eq("id", user_id).execute()
    return result.data[0]


@router.post("/mood")
async def checkin_mood(request: Request, body: MoodCheckin) -> dict[str, str]:
    user_id = get_user_id(request)
    await brief_svc.save_mood(user_id, body.mood)
    return {"message": f"Mood set to '{body.mood}'. Adjusting your day accordingly."}
