"""
Model tests — focus on constraints, FK cascades, and relationships.
Not testing trivial DB round-trips.
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AgentDecision, AdminFeedback, Message, OutboundReply, Thread, ThreadMessage, VoiceSession
from app.models.enums import Action, Channel, FeedbackType, Priority, SenderType, Status


@pytest.fixture
def session(db_session):
    return db_session()


# ---------------------------------------------------------------------------
# FK cascade: deleting a thread removes its decisions and replies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cascade_delete_removes_decisions_and_replies(session):
    async with session as s:
        thread = Thread(priority=Priority.high, status=Status.new)
        s.add(thread)
        await s.flush()

        decision = AgentDecision(
            thread_id=thread.id, action=Action.draft_reply,
            rationale="r", model_id="m", few_shot_ids=[],
        )
        reply = OutboundReply(thread_id=thread.id, final_body="body", channel=Channel.email)
        s.add_all([decision, reply])
        await s.flush()

        decision_id = decision.id
        reply_id = reply.id

        await s.delete(thread)
        await s.commit()

        assert await s.get(AgentDecision, decision_id) is None
        assert await s.get(OutboundReply, reply_id) is None


# ---------------------------------------------------------------------------
# Many-to-many: a message can belong to multiple threads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_message_belongs_to_multiple_threads(session):
    async with session as s:
        msg = Message(channel=Channel.sms, raw_content="leak", sender_ref="+1", sender_type=SenderType.resident)
        t1 = Thread(priority=Priority.low, status=Status.new)
        t2 = Thread(priority=Priority.urgent, status=Status.escalated)
        s.add_all([msg, t1, t2])
        await s.flush()

        s.add_all([ThreadMessage(thread_id=t1.id, message_id=msg.id),
                   ThreadMessage(thread_id=t2.id, message_id=msg.id)])
        await s.commit()

        result = await s.execute(select(ThreadMessage).where(ThreadMessage.message_id == msg.id))
        rows = result.scalars().all()
        assert {r.thread_id for r in rows} == {t1.id, t2.id}


# ---------------------------------------------------------------------------
# Unique constraint on voice_sessions.call_sid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_call_sid_raises(session):
    async with session as s:
        sid = f"CA{uuid.uuid4().hex}"
        s.add(VoiceSession(call_sid=sid, briefing_text="b1", threads_covered=[]))
        await s.commit()

    async with session as s:
        s.add(VoiceSession(call_sid=sid, briefing_text="b2", threads_covered=[]))
        with pytest.raises(IntegrityError):
            await s.commit()


# ---------------------------------------------------------------------------
# admin_feedback requires a valid decision FK
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feedback_without_decision_raises(session):
    async with session as s:
        feedback = AdminFeedback(
            decision_id=uuid.uuid4(),  # non-existent
            feedback_type=FeedbackType.corrected,
            original_action=Action.no_action,
        )
        s.add(feedback)
        with pytest.raises(IntegrityError):
            await s.commit()
