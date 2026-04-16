import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models import AgentDecision, Message, Thread, ThreadMessage
from app.models.enums import Action, Category, Channel, Priority, SenderType, Status
from app.services.tools import (
    TOOLS,
    classify_and_set_category,
    draft_reply,
    escalate,
    group_messages,
    mark_no_action,
    search_similar_threads,
)

FAKE_EMBEDDING = [0.1] * 1536


@pytest.fixture
def session(db_session):
    return db_session()

EXPECTED_TOOL_NAMES = {
    "classify_and_set_category",
    "group_messages",
    "draft_reply",
    "escalate",
    "search_similar_threads",
    "mark_no_action",
}


def test_tools_list_has_six_entries():
    assert len(TOOLS) == 6


def test_each_tool_has_required_keys():
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_tool_names_match_expected():
    names = {t["name"] for t in TOOLS}
    assert names == EXPECTED_TOOL_NAMES


def test_each_input_schema_is_object():
    for tool in TOOLS:
        assert tool["input_schema"]["type"] == "object"


def test_classify_and_set_category_schema():
    tool = next(t for t in TOOLS if t["name"] == "classify_and_set_category")
    props = tool["input_schema"]["properties"]
    assert "category" in props
    assert "priority" in props
    assert set(tool["input_schema"]["required"]) == {"category", "priority"}
    # enum values must match ORM enums
    assert "maintenance" in props["category"]["enum"]
    assert "high" in props["priority"]["enum"]


def test_group_messages_schema():
    tool = next(t for t in TOOLS if t["name"] == "group_messages")
    props = tool["input_schema"]["properties"]
    assert "message_ids" in props
    assert props["message_ids"]["type"] == "array"
    assert "message_ids" in tool["input_schema"]["required"]


def test_draft_reply_schema():
    tool = next(t for t in TOOLS if t["name"] == "draft_reply")
    props = tool["input_schema"]["properties"]
    assert "draft_text" in props
    assert props["draft_text"]["type"] == "string"
    assert "draft_text" in tool["input_schema"]["required"]


def test_escalate_schema_has_no_required_properties():
    tool = next(t for t in TOOLS if t["name"] == "escalate")
    assert tool["input_schema"].get("required", []) == []


def test_search_similar_threads_schema():
    tool = next(t for t in TOOLS if t["name"] == "search_similar_threads")
    props = tool["input_schema"]["properties"]
    assert "query" in props
    assert props["query"]["type"] == "string"
    assert "query" in tool["input_schema"]["required"]


def test_mark_no_action_schema():
    tool = next(t for t in TOOLS if t["name"] == "mark_no_action")
    props = tool["input_schema"]["properties"]
    assert "rationale" in props
    assert props["rationale"]["type"] == "string"
    assert "rationale" in tool["input_schema"]["required"]


# ---------------------------------------------------------------------------
# Async tool implementation tests
# ---------------------------------------------------------------------------


async def test_classify_and_set_category_sets_fields(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()
        result = await classify_and_set_category(
            s, thread.id, category="maintenance", priority="high"
        )
        await s.refresh(thread)
        assert thread.category == Category.maintenance
        assert thread.priority == Priority.high
        assert result["ok"] is True


async def test_group_messages_adds_new_messages(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg1 = Message(
            channel=Channel.email,
            raw_content="Leak in bathroom",
            sender_ref="jan@gmail.com",
            sender_type=SenderType.resident,
        )
        msg2 = Message(
            channel=Channel.sms,
            raw_content="Still leaking",
            sender_ref="+48123456789",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg1, msg2])
        await s.flush()

        result = await group_messages(s, thread.id, message_ids=[str(msg1.id), str(msg2.id)])
        await s.flush()

        from sqlalchemy import select
        rows = (await s.execute(
            select(ThreadMessage).where(ThreadMessage.thread_id == thread.id)
        )).scalars().all()
        assert len(rows) == 2
        assert result["ok"] is True
        assert len(result["added"]) == 2


async def test_group_messages_is_idempotent(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Test",
            sender_ref="a@b.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()

        await group_messages(s, thread.id, message_ids=[str(msg.id)])
        result = await group_messages(s, thread.id, message_ids=[str(msg.id)])
        # Second call adds nothing
        assert result["added"] == []


async def test_draft_reply_stores_text_on_decision(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()
        decision = AgentDecision(
            thread_id=thread.id,
            action=Action.no_action,
            rationale="",
            model_id="claude-sonnet-4-6",
            is_current=True,
        )
        s.add(decision)
        await s.flush()

        result = await draft_reply(s, thread.id, draft_text="Dear Jan, we will fix this.")
        await s.refresh(decision)
        assert decision.draft_reply == "Dear Jan, we will fix this."
        assert result["ok"] is True


async def test_escalate_sets_status_and_priority(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()

        result = await escalate(s, thread.id)
        await s.refresh(thread)
        assert thread.status == Status.escalated
        assert thread.priority == Priority.urgent
        assert result["ok"] is True


async def test_search_similar_threads_returns_context_dict(session):
    async with session as s:
        with patch(
            "app.services.embeddings.generate_embedding",
            new=AsyncMock(return_value=FAKE_EMBEDDING),
        ):
            result = await search_similar_threads(s, uuid.uuid4(), query="broken gate")
        assert "similar_threads" in result
        assert isinstance(result["similar_threads"], list)


async def test_mark_no_action_returns_ok(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()

        result = await mark_no_action(s, thread.id, rationale="Spam message")
        await s.refresh(thread)
        assert result["ok"] is True
        assert result["rationale"] == "Spam message"
        assert thread.status == Status.resolved
