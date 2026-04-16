from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Action


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    action: Action
    rationale: str
    draft_reply: str | None
    model_id: str
    few_shot_ids: list[uuid.UUID]
    is_current: bool
    created_at: datetime
