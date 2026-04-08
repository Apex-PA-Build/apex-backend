import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

SUPPORTED_PROVIDERS = (
    "google",
    "outlook",
    "slack",
    "notion",
    "linear",
    "todoist",
    "spotify",
    "zoom",
    "splitwise",
)


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)   # AES-256-GCM encrypted
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)           # AES-256-GCM encrypted
    scope: Mapped[str | None] = mapped_column(Text)
    external_user_id: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="integrations")

    def __repr__(self) -> str:
        return f"<Integration user={self.user_id} provider={self.provider} active={self.is_active}>"
