from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
    TOKEN_TYPE_REFRESH,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserRead

router = APIRouter()


def _get_current_user_id(request: Request) -> str:
    user_id: str | None = getattr(request.state, "user_id", None)
    if not user_id:
        raise AuthError("Not authenticated")
    return user_id


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Email {data.email} is already registered")
    user = User(
        email=data.email,
        name=data.name,
        hashed_password=hash_password(data.password),
        timezone=data.timezone,
    )
    db.add(user)
    await db.flush()
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account is deactivated")
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request) -> TokenResponse:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("Missing refresh token")
    token = auth.removeprefix("Bearer ").strip()
    user_id = get_user_id_from_token(token, expected_type=TOKEN_TYPE_REFRESH)
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserRead)
async def me(request: Request, db: AsyncSession = Depends(get_db)) -> UserRead:
    user_id = _get_current_user_id(request)
    result = await db.execute(select(User).where(User.id == user_id))  # type: ignore[arg-type]
    user = result.scalar_one_or_none()
    if not user:
        raise AuthError("User not found")
    return UserRead.model_validate(user)


@router.post("/logout", status_code=204)
async def logout() -> None:
    # Stateless JWT: client discards token.
    # For token revocation, push jti to a Redis blocklist here.
    return None
