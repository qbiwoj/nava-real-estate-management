from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Action, FeedbackType


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_type: FeedbackType
    corrected_action: Action | None = None
    corrected_draft: str | None = None
    correction_note: str | None = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    decision_id: uuid.UUID
    feedback_type: FeedbackType
    original_action: Action
    original_draft: str | None
    corrected_action: Action | None
    corrected_draft: str | None
    correction_note: str | None
    created_at: datetime
