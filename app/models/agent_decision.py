import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Action


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE")
    )
    action: Mapped[Action] = mapped_column(Enum(Action, native_enum=True))
    rationale: Mapped[str] = mapped_column(Text)
    draft_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str] = mapped_column(Text)
    few_shot_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    thread: Mapped["Thread"] = relationship(  # noqa: F821
        "Thread", back_populates="decisions"
    )
    feedback: Mapped[list["AdminFeedback"]] = relationship(  # noqa: F821
        "AdminFeedback", back_populates="decision", cascade="all, delete-orphan"
    )
