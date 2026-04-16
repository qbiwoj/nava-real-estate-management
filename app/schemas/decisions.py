from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import Action
from app.services.costs import compute_llm_cost


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
