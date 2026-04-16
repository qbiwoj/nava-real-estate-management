from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class EmailWebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str = Field(..., alias="from")
    subject: str
    body: str
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def sender_ref(self) -> str:
        return self.from_


class SMSWebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str = Field(..., alias="from")
    body: str
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def sender_ref(self) -> str:
        return self.from_


class VoicemailWebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str = Field(..., alias="from")
    audio_url: str
    transcription: str | None = None
    transcription_confidence: float | None = None
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def sender_ref(self) -> str:
        return self.from_
