from pydantic import BaseModel


class IntegrationRead(BaseModel):
    provider: str
    is_active: bool
    scope: str | None
    external_user_id: str | None
    expires_at: str | None
    created_at: str


class AuthURLResponse(BaseModel):
    url: str
    provider: str
