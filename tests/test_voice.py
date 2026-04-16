"""Tests for app/services/voice.py and app/routers/voice.py"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Message, Thread, ThreadMessage
from app.models.enums import Channel, Priority, SenderType, Status


@pytest.fixture
def session(db_session):
    return db_session()


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _mock_anthropic_response(text: str):
    response = MagicMock()
    response.content = [_make_text_block(text)]
    return response


# ---------------------------------------------------------------------------
# POST /voice/inbound
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_voice_inbound(session, async_client):
    """SSML is returned and VoiceSession is persisted with correct threads_covered."""
    from sqlalchemy import select
    from app.models.voice_session import VoiceSession

    async with session as s:
        thread = Thread(priority=Priority.high, status=Status.pending_review)
        msg = Message(
            channel=Channel.email,
            raw_content="Broken heating in apartment 12",
            sender_ref="resident@example.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.commit()
        thread_id = thread.id

    briefing = "You have 1 open item. High priority: maintenance — broken heating."

    with patch(
        "app.services.voice.anthropic_client.messages.create",
        new=AsyncMock(return_value=_mock_anthropic_response(briefing)),
    ):
        resp = await async_client.post(
            "/api/v1/voice/inbound", json={"call_sid": "test-call-001"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ssml"].startswith("<speak>")
    assert "</speak>" in data["ssml"] or data["ssml"].endswith("</speak>")
    assert briefing.split("\n")[0] in data["ssml"]

    async with session as s:
        result = await s.execute(
            select(VoiceSession).where(VoiceSession.call_sid == "test-call-001")
        )
        vs = result.scalar_one_or_none()
        assert vs is not None
        assert str(thread_id) in [str(t) for t in vs.threads_covered]


# ---------------------------------------------------------------------------
# GET /voice/briefing-text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_voice_briefing_text(async_client):
    """Plain text endpoint returns non-empty text and thread list."""
    briefing = "You have 1 open item requiring attention."

    with patch(
        "app.services.voice.anthropic_client.messages.create",
        new=AsyncMock(return_value=_mock_anthropic_response(briefing)),
    ):
        resp = await async_client.get("/api/v1/voice/briefing-text")

    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == briefing
    assert isinstance(data["threads_covered"], list)
