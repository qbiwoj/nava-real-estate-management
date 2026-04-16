from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VoiceInboundRequest(BaseModel):
    call_sid: str


class VoiceInboundResponse(BaseModel):
    ssml: str


class VoiceBriefingTextResponse(BaseModel):
    text: str
    threads_covered: list[uuid.UUID]


class VoiceSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_sid: str
    briefing_text: str
    threads_covered: list[uuid.UUID]
    created_at: datetime
