from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────
    app_name: str = "APEX"
    env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Supabase ─────────────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # ── Anthropic (Claude) ────────────────────────────────────────────
    anthropic_api_key: str
    model_large: str = "claude-opus-4-7"             # morning briefs, complex reasoning
    model_medium: str = "claude-sonnet-4-6"          # chat, call extraction
    model_small: str = "claude-haiku-4-5-20251001"   # classification, memory extraction

    # ── Embeddings (local sentence-transformers) ──────────────────────
    embedding_dim: int = 384

    # ── Redis ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── OAuth Integrations ────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/callback/google"
    slack_client_id: str = ""
    slack_client_secret: str = ""
    notion_client_id: str = ""
    notion_client_secret: str = ""
    zoom_client_id: str = ""
    zoom_client_secret: str = ""

    # ── Security ─────────────────────────────────────────────────────
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str

    # ── CORS — stored as a comma-separated string, exposed as a list ──
    # In .env use: ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
    allowed_origins_raw: str = "http://localhost:3000,http://localhost:3001"

    # ── Rate Limiting ─────────────────────────────────────────────────
    rate_limit_requests: int = 60
    rate_limit_window: int = 60  # seconds

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins_raw.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
