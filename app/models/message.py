import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Channel, SenderType


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel: Mapped[Channel] = mapped_column(Enum(Channel, native_enum=True))
    raw_content: Mapped[str] = mapped_column(Text)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sender_ref: Mapped[str] = mapped_column(String(500))
    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType, native_enum=True))
    transcription_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)

    # relationships
    threads: Mapped[list["Thread"]] = relationship(  # noqa: F821
        "Thread", secondary="thread_messages", back_populates="messages"
    )
