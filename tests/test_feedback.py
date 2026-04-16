"""Tests for app/services/feedback.py"""
import pytest

from app.models import AdminFeedback, AgentDecision, Message, Thread, ThreadMessage
from app.models.enums import Action, Channel, FeedbackType, Priority, SenderType, Status
from app.services.feedback import format_few_shot_examples, retrieve_similar_corrections

FAKE_EMBEDDING = [0.5] * 1536


@pytest.fixture
def session(db_session):
    return db_session()


async def test_retrieve_returns_empty_when_no_feedback(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Gate broken",
            sender_ref="jan@gmail.com",
            sender_type=SenderType.resident,
            embedding=FAKE_EMBEDDING,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))
        await s.flush()

        results = await retrieve_similar_corrections(s, thread.id, top_n=5)
        assert results == []


async def test_retrieve_filters_out_approved_feedback(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Noisy neighbours",
            sender_ref="anna@wp.pl",
            sender_type=SenderType.resident,
            embedding=FAKE_EMBEDDING,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))

        decision = AgentDecision(
            thread_id=thread.id,
            action=Action.draft_reply,
            rationale="Drafted reply",
            model_id="claude-sonnet-4-6",
            is_current=True,
        )
        s.add(decision)
        await s.flush()

        # approved feedback — should NOT be returned
        approved = AdminFeedback(
            decision_id=decision.id,
            feedback_type=FeedbackType.approved,
            original_action=Action.draft_reply,
            embedding=FAKE_EMBEDDING,
        )
        s.add(approved)
        await s.flush()

        results = await retrieve_similar_corrections(s, thread.id, top_n=5)
        assert results == []


async def test_retrieve_returns_corrected_and_overridden_feedback(session):
    async with session as s:
        thread = Thread(priority=Priority.low, status=Status.new)
        msg = Message(
            channel=Channel.email,
            raw_content="Heating not working",
            sender_ref="piotr@gmail.com",
            sender_type=SenderType.resident,
            embedding=FAKE_EMBEDDING,
        )
        s.add_all([thread, msg])
        await s.flush()
        s.add(ThreadMessage(thread_id=thread.id, message_id=msg.id))

        decision = AgentDecision(
            thread_id=thread.id,
            action=Action.no_action,
            rationale="Ignored",
            model_id="claude-sonnet-4-6",
            is_current=True,
        )
        s.add(decision)
        await s.flush()

        corrected = AdminFeedback(
            decision_id=decision.id,
            feedback_type=FeedbackType.corrected,
            original_action=Action.no_action,
            corrected_action=Action.escalate,
            correction_note="Should have escalated heating issue",
            embedding=FAKE_EMBEDDING,
        )
        s.add(corrected)
        await s.flush()

        results = await retrieve_similar_corrections(s, thread.id, top_n=5)
        assert len(results) == 1
        assert results[0].feedback_type == FeedbackType.corrected


def test_format_few_shot_examples_returns_empty_string_for_no_corrections():
    result = format_few_shot_examples([])
    assert result == ""


def test_format_few_shot_examples_includes_correction_note():
    class FakeFeedback:
        correction_note = "Should escalate heating issues"
        original_action = Action.no_action
        corrected_action = Action.escalate
        corrected_draft = None

    result = format_few_shot_examples([FakeFeedback()])
    assert isinstance(result, str)
    assert len(result) > 0
    assert "escalate" in result.lower() or "no_action" in result.lower()
