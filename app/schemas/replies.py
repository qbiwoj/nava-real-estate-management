from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Channel


class SendReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_body: str
    channel: Channel


class ReplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    final_body: str
    channel: Channel
    status: str
    sent_at: datetime | None
    created_at: datetime
