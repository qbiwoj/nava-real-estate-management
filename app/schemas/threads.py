from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import Action, Category, Channel, Priority, SenderType, Status
from app.services.costs import compute_llm_cost


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
    model_id: str
    few_shot_ids: list[uuid.UUID]
    is_current: bool
    created_at: datetime
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None

    @computed_field  # type: ignore[misc]
    @property
    def cost_usd(self) -> float | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return compute_llm_cost(
            self.model_id,
            self.input_tokens,
            self.output_tokens,
            self.cache_read_tokens or 0,
            self.cache_creation_tokens or 0,
        )


class ThreadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: Category | None
    priority: Priority
    status: Status
    created_at: datetime
    updated_at: datetime
    sender_ref: str | None = None
    preview: str | None = None


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
