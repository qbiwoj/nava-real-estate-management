"""Tests for thread/decision routers (Step 6)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import AgentDecision, Message, Thread, ThreadMessage
from app.models.enums import Action, Category, Channel, Priority, SenderType, Status

FAKE_EMBEDDING = [0.2] * 1536


def _make_end_turn_response(text="Done."):
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [MagicMock(type="text", text=text)]
    return response


# ---------------------------------------------------------------------------
# GET /api/v1/threads
# ---------------------------------------------------------------------------


async def test_get_threads_returns_list(async_client, db_session):
    async with db_session() as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.commit()

    r = await async_client.get("/api/v1/threads")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


async def test_get_threads_filter_by_status(async_client, db_session):
    async with db_session() as s:
        t1 = Thread(priority=Priority.low, status=Status.new)
        t2 = Thread(priority=Priority.low, status=Status.resolved)
        s.add_all([t1, t2])
        await s.commit()

    r = await async_client.get("/api/v1/threads?status=new")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "new"


# ---------------------------------------------------------------------------
# GET /api/v1/threads/{id}
# ---------------------------------------------------------------------------


async def test_get_thread_detail(async_client, db_session):
    async with db_session() as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Hello",
            sender_ref="a@b.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.commit()
        tid = str(thread.id)

    r = await async_client.get(f"/api/v1/threads/{tid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == tid
    assert "messages" in data


async def test_get_thread_returns_404_for_unknown_id(async_client):
    import uuid
    r = await async_client.get(f"/api/v1/threads/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/threads/{id}
# ---------------------------------------------------------------------------


async def test_patch_thread_updates_status(async_client, db_session):
    async with db_session() as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.commit()
        tid = str(thread.id)

    r = await async_client.patch(
        f"/api/v1/threads/{tid}",
        json={"status": "resolved"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


async def test_patch_thread_updates_priority(async_client, db_session):
    async with db_session() as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.commit()
        tid = str(thread.id)

    r = await async_client.patch(
        f"/api/v1/threads/{tid}",
        json={"priority": "urgent"},
    )
    assert r.status_code == 200
    assert r.json()["priority"] == "urgent"


async def test_patch_thread_returns_404_for_unknown(async_client):
    import uuid
    r = await async_client.patch(
        f"/api/v1/threads/{uuid.uuid4()}",
        json={"status": "resolved"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/threads/{id}/run-agent
# ---------------------------------------------------------------------------


async def test_post_run_agent_returns_decision(async_client, db_session):
    async with db_session() as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Leaking pipe",
            sender_ref="p@test.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.commit()
        tid = str(thread.id)

    with patch(
        "app.services.agent.anthropic_client.messages.create",
        new=AsyncMock(return_value=_make_end_turn_response()),
    ):
        r = await async_client.post(f"/api/v1/threads/{tid}/run-agent")

    assert r.status_code == 200
    data = r.json()
    assert "decision_id" in data
    assert "action" in data
    assert "rationale" in data


async def test_post_run_agent_returns_404_for_unknown_thread(async_client):
    import uuid
    with patch(
        "app.services.agent.anthropic_client.messages.create",
        new=AsyncMock(return_value=_make_end_turn_response()),
    ):
        r = await async_client.post(f"/api/v1/threads/{uuid.uuid4()}/run-agent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/threads/{id}/decisions
# ---------------------------------------------------------------------------


async def test_get_thread_decisions_returns_list(async_client, db_session):
    async with db_session() as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()
        decision = AgentDecision(
            thread_id=thread.id,
            action=Action.no_action,
            rationale="Test",
            model_id="claude-sonnet-4-6",
            is_current=True,
        )
        s.add(decision)
        await s.commit()
        tid = str(thread.id)
        did = str(decision.id)

    r = await async_client.get(f"/api/v1/threads/{tid}/decisions")
    assert r.status_code == 200
    items = r.json()
    assert any(d["id"] == did for d in items)


# ---------------------------------------------------------------------------
# GET /api/v1/decisions/{id}
# ---------------------------------------------------------------------------


async def test_get_decision_by_id(async_client, db_session):
    async with db_session() as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()
        decision = AgentDecision(
            thread_id=thread.id,
            action=Action.draft_reply,
            rationale="Drafted reply for resident",
            draft_reply="Dear resident, we will fix this soon.",
            model_id="claude-sonnet-4-6",
            is_current=True,
        )
        s.add(decision)
        await s.commit()
        did = str(decision.id)

    r = await async_client.get(f"/api/v1/decisions/{did}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == did
    assert data["action"] == "draft_reply"
    assert data["is_current"] is True


async def test_get_decision_returns_404_for_unknown(async_client):
    import uuid
    r = await async_client.get(f"/api/v1/decisions/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Step 7 — End-to-end smoke test
# ---------------------------------------------------------------------------


async def test_webhook_to_agent_to_decision_pipeline(async_client):
    """Full pipeline: webhook → ingest → run-agent → GET decisions → GET decision."""
    end_turn = MagicMock()
    end_turn.stop_reason = "end_turn"
    end_turn.content = [MagicMock(type="text", text="Classified as maintenance.")]

    with patch(
        "app.services.ingestion._embeddings.generate_embedding",
        new=AsyncMock(return_value=FAKE_EMBEDDING),
    ):
        r1 = await async_client.post(
            "/api/v1/webhooks/email",
            json={"from": "jan@gmail.com", "subject": "Gate broken", "body": "The front gate is not working."},
        )
    assert r1.status_code == 202
    thread_id = r1.json()["thread_id"]

    with patch(
        "app.services.agent.anthropic_client.messages.create",
        new=AsyncMock(return_value=end_turn),
    ):
        r2 = await async_client.post(f"/api/v1/threads/{thread_id}/run-agent")
    assert r2.status_code == 200
    decision_id = r2.json()["decision_id"]

    r3 = await async_client.get(f"/api/v1/threads/{thread_id}/decisions")
    assert r3.status_code == 200
    assert any(d["id"] == decision_id for d in r3.json())

    r4 = await async_client.get(f"/api/v1/decisions/{decision_id}")
    assert r4.status_code == 200
    assert r4.json()["is_current"] is True
    assert r4.json()["thread_id"] == thread_id
