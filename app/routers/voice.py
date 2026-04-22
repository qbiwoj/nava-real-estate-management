from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.briefing import Briefing
from app.models.voice_session import VoiceSession
from app.schemas.voice import (
    VoiceBriefingTextResponse,
    VoiceInboundRequest,
    VoiceInboundResponse,
    VoiceSessionResponse,
)
from app.services.voice import format_as_ssml, generate_queue_briefing, get_or_generate_briefing, synthesize_speech

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.post("/inbound", response_model=VoiceInboundResponse)
async def voice_inbound(
    body: VoiceInboundRequest,
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(
        select(VoiceSession).where(VoiceSession.call_sid == body.call_sid)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="call_sid already exists")

    briefing_text, thread_ids = await get_or_generate_briefing(session)
    ssml = format_as_ssml(briefing_text)

    voice_session = VoiceSession(
        call_sid=body.call_sid,
        briefing_text=briefing_text,
        threads_covered=thread_ids,
    )
    session.add(voice_session)
    await session.commit()

    return VoiceInboundResponse(ssml=ssml)


@router.get("/briefing-text", response_model=VoiceBriefingTextResponse)
async def briefing_text(
    session: AsyncSession = Depends(get_session),
):
    text, thread_ids = await get_or_generate_briefing(session)
    return VoiceBriefingTextResponse(text=text, threads_covered=thread_ids)


@router.post("/briefing/refresh", response_model=VoiceBriefingTextResponse)
async def refresh_briefing(
    session: AsyncSession = Depends(get_session),
):
    """Force-generate a new briefing and store it, replacing the cached one."""
    await session.execute(delete(Briefing))
    text, thread_ids = await generate_queue_briefing(session)
    session.add(Briefing(briefing_text=text, threads_covered=thread_ids))
    await session.commit()
    return VoiceBriefingTextResponse(text=text, threads_covered=thread_ids)


@router.get("/briefing-audio")
async def briefing_audio(
    session: AsyncSession = Depends(get_session),
):
    text, _ = await get_or_generate_briefing(session)
    audio = await synthesize_speech(text)
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/sessions/{call_sid}/end", response_model=VoiceSessionResponse)
async def end_session(
    call_sid: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(VoiceSession).where(VoiceSession.call_sid == call_sid)
    )
    voice_session = result.scalar_one_or_none()
    if voice_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return voice_session
