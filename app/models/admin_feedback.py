import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Action, FeedbackType


class AdminFeedback(Base):
    __tablename__ = "admin_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_decisions.id", ondelete="CASCADE")
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(Enum(FeedbackType, native_enum=True))
    original_action: Mapped[Action] = mapped_column(Enum(Action, native_enum=True, create_type=False))
    corrected_action: Mapped[Action | None] = mapped_column(
        Enum(Action, native_enum=True, create_type=False), nullable=True
    )
    original_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    decision: Mapped["AgentDecision"] = relationship(  # noqa: F821
        "AgentDecision", back_populates="feedback"
    )
