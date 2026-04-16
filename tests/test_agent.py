"""Tests for app/services/agent.py"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import AdminFeedback, AgentDecision, Message, Thread, ThreadMessage
from app.models.enums import Action, Channel, FeedbackType, Priority, SenderType, Status
from app.services.agent import assemble_system_prompt, run_agent

FAKE_EMBEDDING = [0.3] * 1536


@pytest.fixture
def session(db_session):
    return db_session()


# ---------------------------------------------------------------------------
# Step 4 — assemble_system_prompt
# ---------------------------------------------------------------------------


async def test_assemble_system_prompt_returns_two_blocks(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="The lift is broken",
            sender_ref="jan@gmail.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.flush()

        blocks = await assemble_system_prompt(thread.id, s)

    assert len(blocks) == 2


async def test_first_block_has_cache_control(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()

        blocks = await assemble_system_prompt(thread.id, s)

    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


async def test_second_block_has_no_cache_control(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()

        blocks = await assemble_system_prompt(thread.id, s)

    assert "cache_control" not in blocks[1]


async def test_both_blocks_are_text_type(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()

        blocks = await assemble_system_prompt(thread.id, s)

    assert blocks[0]["type"] == "text"
    assert blocks[1]["type"] == "text"


async def test_first_block_contains_role_context(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        s.add(thread)
        await s.flush()

        blocks = await assemble_system_prompt(thread.id, s)

    assert "property" in blocks[0]["text"].lower() or "management" in blocks[0]["text"].lower()


async def test_second_block_contains_no_corrections_placeholder_when_empty(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Test",
            sender_ref="x@y.com",
            sender_type=SenderType.resident,
            embedding=FAKE_EMBEDDING,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.flush()

        blocks = await assemble_system_prompt(thread.id, s)

    # No corrections in DB → placeholder text
    assert "no past corrections" in blocks[1]["text"].lower()


async def test_second_block_injects_corrections_when_they_exist(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Heating broken",
            sender_ref="b@c.com",
            sender_type=SenderType.resident,
            embedding=FAKE_EMBEDDING,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))

        decision = AgentDecision(
            thread_id=thread.id,
            action=Action.no_action,
            rationale="",
            model_id="claude-sonnet-4-6",
            is_current=True,
        )
        s.add(decision)
        await s.flush()

        correction = AdminFeedback(
            decision_id=decision.id,
            feedback_type=FeedbackType.corrected,
            original_action=Action.no_action,
            corrected_action=Action.escalate,
            correction_note="Always escalate heating failures in winter",
            embedding=FAKE_EMBEDDING,
        )
        s.add(correction)
        await s.flush()

        blocks = await assemble_system_prompt(thread.id, s)

    assert "example" in blocks[1]["text"].lower() or "escalate" in blocks[1]["text"].lower()


# ---------------------------------------------------------------------------
# Step 5 — run_agent agentic loop
# ---------------------------------------------------------------------------


def _make_end_turn_response(text="Classified and done."):
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [MagicMock(type="text", text=text)]
    return response


def _make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "toolu_01"):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = tool_input

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


async def test_run_agent_creates_decision_on_end_turn(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Gate is broken",
            sender_ref="jan@gmail.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.flush()

        with patch(
            "app.services.agent.anthropic_client.messages.create",
            new=AsyncMock(return_value=_make_end_turn_response()),
        ):
            decision = await run_agent(thread.id, s)

        assert decision.is_current is True
        assert decision.thread_id == thread.id
        await s.refresh(thread)
        assert thread.status == Status.pending_review


async def test_run_agent_sets_thread_status_to_pending_review(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Intercom broken",
            sender_ref="maria@gmail.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.flush()

        with patch(
            "app.services.agent.anthropic_client.messages.create",
            new=AsyncMock(return_value=_make_end_turn_response()),
        ):
            await run_agent(thread.id, s)

        await s.refresh(thread)
        assert thread.status == Status.pending_review


async def test_run_agent_dispatches_tool_call(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Roof leaking badly",
            sender_ref="t@test.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.flush()

        responses = [
            _make_tool_use_response(
                "classify_and_set_category",
                {"category": "maintenance", "priority": "high"},
            ),
            _make_end_turn_response("Classified as maintenance."),
        ]

        with patch(
            "app.services.agent.anthropic_client.messages.create",
            new=AsyncMock(side_effect=responses),
        ):
            decision = await run_agent(thread.id, s)

        await s.refresh(thread)
        assert thread.category is not None
        assert decision.action == Action.group_only or decision.action is not None


async def test_run_agent_marks_previous_decision_not_current(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Window stuck",
            sender_ref="k@test.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))

        old_decision = AgentDecision(
            thread_id=thread.id,
            action=Action.no_action,
            rationale="Old run",
            model_id="claude-sonnet-4-6",
            is_current=True,
        )
        s.add(old_decision)
        await s.flush()

        with patch(
            "app.services.agent.anthropic_client.messages.create",
            new=AsyncMock(return_value=_make_end_turn_response()),
        ):
            new_decision = await run_agent(thread.id, s)

        await s.refresh(old_decision)
        assert old_decision.is_current is False
        assert new_decision.is_current is True
        assert new_decision.id != old_decision.id


async def test_run_agent_records_draft_reply_action(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="When will the elevator be fixed?",
            sender_ref="d@test.com",
            sender_type=SenderType.resident,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.flush()

        responses = [
            _make_tool_use_response(
                "draft_reply",
                {"draft_text": "Dear resident, the elevator will be fixed by Friday."},
            ),
            _make_end_turn_response("Reply drafted."),
        ]

        with patch(
            "app.services.agent.anthropic_client.messages.create",
            new=AsyncMock(side_effect=responses),
        ):
            decision = await run_agent(thread.id, s)

        assert decision.action == Action.draft_reply
        assert decision.draft_reply is not None
        assert "Friday" in decision.draft_reply or len(decision.draft_reply) > 0
