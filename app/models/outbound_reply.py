import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Channel


class OutboundReply(Base):
    __tablename__ = "outbound_replies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE")
    )
    final_body: Mapped[str] = mapped_column(Text)
    channel: Mapped[Channel] = mapped_column(Enum(Channel, native_enum=True))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    thread: Mapped["Thread"] = relationship(  # noqa: F821
        "Thread", back_populates="replies"
    )
