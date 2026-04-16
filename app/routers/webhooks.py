from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.webhooks import EmailWebhookPayload, SMSWebhookPayload, VoicemailWebhookPayload
from app.services.ingestion import ingest_message

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/email", status_code=202)
async def receive_email(
    payload: EmailWebhookPayload,
    session: AsyncSession = Depends(get_session),
):
    msg, thread = await ingest_message(
        session=session,
        channel="email",
        raw_content=payload.body,
        subject=payload.subject,
        sender_ref=payload.sender_ref,
        received_at=payload.received_at,
    )
    await session.commit()
    # TODO Session 3: trigger agent background task
    return {"message_id": str(msg.id), "thread_id": str(thread.id)}


@router.post("/sms", status_code=202)
async def receive_sms(
    payload: SMSWebhookPayload,
    session: AsyncSession = Depends(get_session),
):
    msg, thread = await ingest_message(
        session=session,
        channel="sms",
        raw_content=payload.body,
        sender_ref=payload.sender_ref,
        received_at=payload.received_at,
    )
    await session.commit()
    return {"message_id": str(msg.id), "thread_id": str(thread.id)}


@router.post("/voicemail", status_code=202)
async def receive_voicemail(
    payload: VoicemailWebhookPayload,
    session: AsyncSession = Depends(get_session),
):
    msg, thread = await ingest_message(
        session=session,
        channel="voicemail",
        raw_content=payload.audio_url,
        sender_ref=payload.sender_ref,
        received_at=payload.received_at,
        transcription=payload.transcription,
        transcription_confidence=payload.transcription_confidence,
    )
    await session.commit()
    return {"message_id": str(msg.id), "thread_id": str(thread.id)}
