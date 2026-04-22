import logging
import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Thread, ThreadMessage
from app.models.enums import Channel, Priority, SenderType, Status
from app.services import embeddings as _embeddings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sender type detection
# ---------------------------------------------------------------------------

# TODO: move to config in Session 6
_SUPPLIER_DOMAINS: set[str] = {"bud-serwis.pl"}
_RESIDENTIAL_EMAIL_PROVIDERS: set[str] = {
    "gmail.com", "wp.pl", "onet.pl", "outlook.com", "hotmail.com",
}
_BOARD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^zarzad@", re.IGNORECASE),
    re.compile(r"\bboard\b", re.IGNORECASE),
]
_PHONE_PATTERN: re.Pattern[str] = re.compile(r"^\+?[\d\s\-]{7,15}$")


def detect_sender_type(sender_ref: str) -> SenderType:
    if not sender_ref:
        return SenderType.unknown
    if any(p.search(sender_ref) for p in _BOARD_PATTERNS):
        return SenderType.board
    if _PHONE_PATTERN.match(sender_ref.strip()):
        return SenderType.resident
    if "@" in sender_ref:
        domain = sender_ref.split("@", 1)[1].lower()
        if domain in _SUPPLIER_DOMAINS:
            return SenderType.supplier
        if domain in _RESIDENTIAL_EMAIL_PROVIDERS:
            return SenderType.resident
    return SenderType.unknown


# ---------------------------------------------------------------------------
# Thread grouping via pgvector
# ---------------------------------------------------------------------------


async def find_or_create_thread(
    session: AsyncSession,
    sender_ref: str,
    embedding: list[float],
    threshold: float | None = None,
) -> Thread:
    """
    Return an existing Thread if the closest message has cosine distance below
    the applicable threshold, else create and return a new Thread.
    Same-sender threshold: 0.25. Cross-sender threshold: 0.40.
    Does NOT commit — caller is responsible.
    """
    same_sender_threshold = threshold if threshold is not None else 0.25
    cross_sender_threshold = 0.40

    sql = text("""
        SELECT tm.thread_id, m.sender_ref, m.embedding <=> CAST(:query_vec AS vector) AS distance
        FROM messages m
        JOIN thread_messages tm ON tm.message_id = m.id
        WHERE m.embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT 1
    """)

    result = await session.execute(
        sql,
        {"query_vec": str(embedding)},
    )
    row = result.fetchone()

    if row is not None:
        applicable_threshold = (
            same_sender_threshold if row.sender_ref == sender_ref else cross_sender_threshold
        )
    else:
        applicable_threshold = same_sender_threshold

    if row is not None and row.distance < applicable_threshold:
        thread = await session.get(Thread, row.thread_id)
        logger.info("thread_matched", extra={
            "event": "thread_matched",
            "sender_ref": sender_ref,
            "thread_id": str(thread.id),
            "distance": round(float(row.distance), 4),
            "threshold": applicable_threshold,
            "cross_sender": row.sender_ref != sender_ref,
        })
        return thread

    thread = Thread(priority=Priority.low, status=Status.new)
    session.add(thread)
    await session.flush()
    logger.info("thread_created", extra={
        "event": "thread_created",
        "sender_ref": sender_ref,
        "thread_id": str(thread.id),
        "distance": round(float(row.distance), 4) if row else None,
        "threshold": applicable_threshold,
    })
    return thread


# ---------------------------------------------------------------------------
# Ingestion orchestrator
# ---------------------------------------------------------------------------


async def ingest_message(
    session: AsyncSession,
    channel: str,
    raw_content: str,
    sender_ref: str,
    subject: str | None = None,
    received_at: datetime | None = None,
    transcription: str | None = None,
    transcription_confidence: float | None = None,
) -> tuple[Message, Thread]:
    """
    Full ingestion pipeline for one incoming message.
    Does NOT commit — caller is responsible.
    Returns (Message, Thread).
    """
    if received_at is None:
        received_at = datetime.now(timezone.utc)

    sender_type = detect_sender_type(sender_ref)

    embed_text = transcription if transcription else raw_content
    embedding = await _embeddings.generate_embedding(embed_text)

    message = Message(
        channel=Channel(channel),
        raw_content=raw_content,
        transcription=transcription,
        transcription_confidence=transcription_confidence,
        subject=subject,
        sender_ref=sender_ref,
        sender_type=sender_type,
        received_at=received_at,
        embedding=embedding,
    )
    session.add(message)
    await session.flush()

    thread = await find_or_create_thread(session, sender_ref, embedding)

    session.add(ThreadMessage(thread_id=thread.id, message_id=message.id))

    logger.info("message_ingested", extra={
        "event": "message_ingested",
        "channel": channel,
        "sender_ref": sender_ref,
        "sender_type": sender_type.value,
    })

    return message, thread
