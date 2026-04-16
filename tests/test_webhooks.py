"""
Webhook tests — schema validation (Step 1) + HTTP integration (Step 6).
"""
import pytest
from pydantic import ValidationError

from app.schemas.webhooks import (
    EmailWebhookPayload,
    SMSWebhookPayload,
    VoicemailWebhookPayload,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_email_schema_valid():
    p = EmailWebhookPayload.model_validate({"from": "jan@example.com", "subject": "Leak", "body": "Water dripping"})
    assert p.sender_ref == "jan@example.com"
    assert p.subject == "Leak"
    assert p.body == "Water dripping"


def test_email_schema_rejects_missing_body():
    with pytest.raises(ValidationError):
        EmailWebhookPayload.model_validate({"from": "jan@example.com", "subject": "Leak"})


def test_email_schema_rejects_extra_fields():
    with pytest.raises(ValidationError):
        EmailWebhookPayload.model_validate(
            {"from": "jan@example.com", "subject": "Leak", "body": "text", "unknown": "x"}
        )


def test_sms_schema_valid():
    p = SMSWebhookPayload.model_validate({"from": "+48601234567", "body": "Heater broken"})
    assert p.sender_ref == "+48601234567"
    assert p.body == "Heater broken"


def test_sms_schema_rejects_missing_body():
    with pytest.raises(ValidationError):
        SMSWebhookPayload.model_validate({"from": "+48601234567"})


def test_voicemail_schema_transcription_optional():
    p = VoicemailWebhookPayload.model_validate(
        {"from": "+48601234567", "audio_url": "https://s3.example/call.mp3"}
    )
    assert p.sender_ref == "+48601234567"
    assert p.transcription is None
    assert p.transcription_confidence is None


def test_voicemail_schema_accepts_transcription_with_confidence():
    p = VoicemailWebhookPayload.model_validate(
        {
            "from": "+48601234567",
            "audio_url": "https://s3.example/call.mp3",
            "transcription": "Water flooding",
            "transcription_confidence": 0.72,
        }
    )
    assert p.transcription == "Water flooding"
    assert p.transcription_confidence == pytest.approx(0.72)


def test_voicemail_schema_rejects_missing_audio_url():
    with pytest.raises(ValidationError):
        VoicemailWebhookPayload.model_validate({"from": "+48601234567"})
