"""
Webhook tests — schema validation (Step 1) + HTTP integration (Step 6).
"""
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch

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


# ---------------------------------------------------------------------------
# Step 6 — HTTP integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_email_webhook_returns_202(async_client):
    with patch(
        "app.services.ingestion._embeddings.generate_embedding",
        new=AsyncMock(return_value=[0.0] * 1536),
    ):
        response = await async_client.post(
            "/api/v1/webhooks/email",
            json={"from": "jan@gmail.com", "subject": "Broken gate", "body": "Gate is open"},
        )
    assert response.status_code == 202
    data = response.json()
    assert "message_id" in data
    assert "thread_id" in data


@pytest.mark.asyncio
async def test_post_sms_webhook_returns_202(async_client):
    with patch(
        "app.services.ingestion._embeddings.generate_embedding",
        new=AsyncMock(return_value=[0.0] * 1536),
    ):
        response = await async_client.post(
            "/api/v1/webhooks/sms",
            json={"from": "+48601234567", "body": "Heater broken"},
        )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_post_voicemail_webhook_returns_202(async_client):
    with patch(
        "app.services.ingestion._embeddings.generate_embedding",
        new=AsyncMock(return_value=[0.0] * 1536),
    ):
        response = await async_client.post(
            "/api/v1/webhooks/voicemail",
            json={
                "from": "+48888100200",
                "audio_url": "https://s3.example/call.mp3",
                "transcription": "Water in basement",
                "transcription_confidence": 0.72,
            },
        )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_post_email_webhook_missing_body_returns_422(async_client):
    response = await async_client.post(
        "/api/v1/webhooks/email",
        json={"from": "jan@gmail.com", "subject": "Broken gate"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_sms_webhook_persists_message(async_client, db_session):
    """Integration: verify a message row is actually written to the test DB."""
    from sqlalchemy import select
    from app.models import Message

    with patch(
        "app.services.ingestion._embeddings.generate_embedding",
        new=AsyncMock(return_value=[0.0] * 1536),
    ):
        response = await async_client.post(
            "/api/v1/webhooks/sms",
            json={"from": "+48999000111", "body": "The lift is broken"},
        )
    assert response.status_code == 202

    async with db_session() as s:
        result = await s.execute(
            select(Message).where(Message.sender_ref == "+48999000111")
        )
        messages = result.scalars().all()
    assert len(messages) >= 1
    assert any(m.raw_content == "The lift is broken" for m in messages)
