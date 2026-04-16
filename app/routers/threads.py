from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import AgentDecision, Message, Thread, ThreadMessage
from app.schemas.threads import (
    RunAgentResponse,
    ThreadListResponse,
    ThreadPatchRequest,
    ThreadResponse,
    ThreadSummary,
)
from app.schemas.decisions import DecisionResponse
from app.services.agent import run_agent

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_session),
):
    query = select(Thread)
    if status:
        query = query.where(Thread.status == status)
    if priority:
        query = query.where(Thread.priority == priority)
    if category:
        query = query.where(Thread.category == category)

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    paginated = (
        query.options(selectinload(Thread.messages))
        .order_by(
            case(
                (Thread.priority == "urgent", 0),
                (Thread.priority == "high", 1),
                (Thread.priority == "medium", 2),
                (Thread.priority == "low", 3),
                else_=4,
            ),
            Thread.created_at.desc(),
        )
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(paginated)
    threads = result.scalars().all()

    def _summary(t: Thread) -> ThreadSummary:
        first = sorted(t.messages, key=lambda m: m.received_at)[0] if t.messages else None
        text = (first.transcription or first.raw_content) if first else None
        preview = (text[:80] + "…") if text and len(text) > 80 else text
        return ThreadSummary(
            id=t.id,
            category=t.category,
            priority=t.priority,
            status=t.status,
            created_at=t.created_at,
            updated_at=t.updated_at,
            sender_ref=first.sender_ref if first else None,
            preview=preview,
        )

    return ThreadListResponse(
        items=[_summary(t) for t in threads],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Thread)
        .options(selectinload(Thread.messages), selectinload(Thread.decisions))
        .where(Thread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    current_decision = next(
        (d for d in sorted(thread.decisions, key=lambda d: d.created_at, reverse=True)
         if d.is_current),
        None,
    )

    return ThreadResponse(
        id=thread.id,
        category=thread.category,
        priority=thread.priority,
        status=thread.status,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        messages=thread.messages,
        current_decision=current_decision,
    )


@router.patch("/{thread_id}", response_model=ThreadSummary)
async def patch_thread(
    thread_id: uuid.UUID,
    body: ThreadPatchRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Thread).where(Thread.id == thread_id))
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    if body.status is not None:
        thread.status = body.status
    if body.priority is not None:
        thread.priority = body.priority

    await session.commit()
    await session.refresh(thread)
    return thread


@router.post("/{thread_id}/run-agent", response_model=RunAgentResponse)
async def trigger_run_agent(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Thread).where(Thread.id == thread_id))
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    decision = await run_agent(thread_id, session)
    return RunAgentResponse(
        decision_id=decision.id,
        action=decision.action,
        rationale=decision.rationale,
        draft_reply=decision.draft_reply,
    )


@router.get("/{thread_id}/decisions", response_model=list[DecisionResponse])
async def list_decisions(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AgentDecision)
        .where(AgentDecision.thread_id == thread_id)
        .order_by(AgentDecision.created_at.desc())
    )
    return list(result.scalars().all())
