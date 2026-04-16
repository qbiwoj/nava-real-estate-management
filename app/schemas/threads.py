from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Action, Category, Channel, Priority, SenderType, Status


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: Channel
    raw_content: str
    transcription: str | None
    subject: str | None
    sender_ref: str
    sender_type: SenderType
    transcription_confidence: float | None
    received_at: datetime


class DecisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: Action
    rationale: str
    draft_reply: str | None
    is_current: bool
    created_at: datetime


class ThreadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: Category | None
    priority: Priority
    status: Status
    created_at: datetime
    updated_at: datetime


class ThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: Category | None
    priority: Priority
    status: Status
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]
    current_decision: DecisionSummary | None


class ThreadListResponse(BaseModel):
    items: list[ThreadSummary]
    total: int
    page: int
    page_size: int


class ThreadPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status | None = None
    priority: Priority | None = None


class RunAgentResponse(BaseModel):
    decision_id: uuid.UUID
    action: Action
    rationale: str
    draft_reply: str | None
