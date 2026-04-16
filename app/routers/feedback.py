from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import AdminFeedback, AgentDecision, Thread
from app.models.enums import FeedbackType
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.feedback import retrieve_similar_corrections, submit_feedback

router = APIRouter(tags=["feedback"])
logger = logging.getLogger(__name__)


@router.post(
    "/api/v1/threads/{thread_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201,
)
async def create_feedback(
    thread_id: uuid.UUID,
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_session),
):
    # Verify thread exists
    thread = await session.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Fetch the current decision
    result = await session.execute(
        select(AgentDecision)
        .where(AgentDecision.thread_id == thread_id, AgentDecision.is_current.is_(True))
        .limit(1)
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise HTTPException(status_code=404, detail="No current decision for this thread")

    feedback = await submit_feedback(
        session=session,
        thread_id=thread_id,
        decision_id=decision.id,
        feedback_type=body.feedback_type,
        original_action=decision.action,
        original_draft=decision.draft_reply,
        corrected_action=body.corrected_action,
        corrected_draft=body.corrected_draft,
        correction_note=body.correction_note,
    )
    await session.commit()
    await session.refresh(feedback)
    logger.info("feedback_submitted", extra={
        "event": "feedback_submitted",
        "thread_id": str(thread_id),
        "decision_id": str(decision.id),
        "feedback_type": body.feedback_type.value,
        "has_corrected_action": body.corrected_action is not None,
    })
    return feedback


@router.get("/api/v1/feedback", response_model=list[FeedbackResponse])
async def list_feedback(
    feedback_type: FeedbackType | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AdminFeedback).order_by(AdminFeedback.created_at.desc())
    if feedback_type is not None:
        stmt = stmt.where(AdminFeedback.feedback_type == feedback_type)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/api/v1/feedback/similar", response_model=list[FeedbackResponse])
async def similar_feedback(
    thread_id: uuid.UUID = Query(...),
    top_n: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
):
    return await retrieve_similar_corrections(session, thread_id, top_n=top_n)
