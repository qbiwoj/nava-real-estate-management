from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import OutboundReply, Thread
from app.models.enums import Status
from app.schemas.replies import ReplyResponse, SendReplyRequest

router = APIRouter(tags=["replies"])


@router.post(
    "/api/v1/threads/{thread_id}/send-reply",
    response_model=ReplyResponse,
    status_code=201,
)
async def send_reply(
    thread_id: uuid.UUID,
    body: SendReplyRequest,
    session: AsyncSession = Depends(get_session),
):
    thread = await session.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    reply = OutboundReply(
        thread_id=thread_id,
        final_body=body.final_body,
        channel=body.channel,
        status="sent",
        sent_at=datetime.now(timezone.utc),
    )
    session.add(reply)
    thread.status = Status.replied
    await session.commit()
    await session.refresh(reply)
    return reply


@router.get(
    "/api/v1/threads/{thread_id}/replies",
    response_model=list[ReplyResponse],
)
async def list_replies(
    thread_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    thread = await session.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    result = await session.execute(
        select(OutboundReply)
        .where(OutboundReply.thread_id == thread_id)
        .order_by(OutboundReply.created_at.desc())
    )
    return result.scalars().all()
