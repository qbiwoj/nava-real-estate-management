import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Category, Priority, Status


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category: Mapped[Category | None] = mapped_column(
        Enum(Category, native_enum=True), nullable=True
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=True), default=Priority.low
    )
    status: Mapped[Status] = mapped_column(
        Enum(Status, native_enum=True), default=Status.new
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", secondary="thread_messages", back_populates="threads"
    )
    decisions: Mapped[list["AgentDecision"]] = relationship(  # noqa: F821
        "AgentDecision", back_populates="thread", cascade="all, delete-orphan"
    )
    replies: Mapped[list["OutboundReply"]] = relationship(  # noqa: F821
        "OutboundReply", back_populates="thread", cascade="all, delete-orphan"
    )
