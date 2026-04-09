import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.goal import Goal
    from app.models.user import User


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|in_progress|done|deferred|cancelled
    priority: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high|critical
    eisenhower_quadrant: Mapped[int | None] = mapped_column(Integer)  # 1=urgent+imp, 2=not urgent+imp, 3=urgent+not imp, 4=neither
    energy_required: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high
    source_integration: Mapped[str | None] = mapped_column(String(64))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="tasks")
    goal: Mapped["Goal | None"] = relationship(back_populates="tasks")
    subtasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="parent_task", cascade="all, delete-orphan"
    )
    parent_task: Mapped["Task | None"] = relationship("Task", back_populates="subtasks", remote_side=[id])

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"
