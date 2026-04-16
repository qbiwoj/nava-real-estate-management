from __future__ import annotations

import uuid

import anthropic
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Message, Thread, ThreadMessage
from app.models.enums import Priority, Status

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

_PRIORITY_ORDER = {
    Priority.urgent: 0,
    Priority.high: 1,
    Priority.medium: 2,
    Priority.low: 3,
}

_BRIEFING_SYSTEM_PROMPT = """Jesteś asystentem głosowym informującym zarządcę nieruchomości o aktualnej kolejce wiadomości.
Wygeneruj bardzo zwięzłe podsumowanie mówione (poniżej 30 sekund podczas czytania na głos).
Zacznij od razu od spraw — bez powitania, bez wstępu.
Dla każdej sprawy: priorytet, kategoria, krótkie hasło. Tylko najważniejsze informacje.
Zakończ łączną liczbą otwartych spraw.
Odpowiadaj wyłącznie po polsku."""


async def generate_queue_briefing(
    session: AsyncSession,
) -> tuple[str, list[uuid.UUID]]:
    """Query open threads, call Claude once, return (briefing_text, thread_ids)."""
    resolved_statuses = {Status.resolved, Status.replied}

    result = await session.execute(
        select(Thread)
        .options(selectinload(Thread.messages))
        .where(Thread.status.notin_(resolved_statuses))
    )
    threads = list(result.scalars().all())

    if not threads:
        return "Brak otwartych spraw w kolejce.", []

    threads.sort(key=lambda t: (_PRIORITY_ORDER.get(t.priority, 99), t.created_at))

    thread_ids: list[uuid.UUID] = []
    lines: list[str] = []

    for t in threads:
        thread_ids.append(t.id)
        msg_result = await session.execute(
            select(Message)
            .join(ThreadMessage, ThreadMessage.message_id == Message.id)
            .where(ThreadMessage.thread_id == t.id)
            .order_by(Message.received_at)
            .limit(1)
        )
        first_msg = msg_result.scalar_one_or_none()
        preview = ""
        if first_msg:
            text = first_msg.transcription or first_msg.raw_content or ""
            preview = text[:60].replace("\n", " ")

        category = t.category.value if t.category else "general"
        priority = t.priority.value if t.priority else "medium"
        msg_count = len(t.messages)
        lines.append(
            f"- [{priority.upper()}] {category} ({msg_count} message{'s' if msg_count != 1 else ''}): {preview}"
        )

    user_content = f"Open threads ({len(threads)} total):\n" + "\n".join(lines)

    response = await anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": _BRIEFING_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    briefing_text = ""
    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            briefing_text = block.text
            break

    return briefing_text, thread_ids


def format_as_ssml(text: str) -> str:
    """Wrap briefing text in SSML <speak> tags with pacing breaks."""
    sentences = [s.strip() for s in text.split("\n") if s.strip()]
    body = '<break time="400ms"/>'.join(sentences)
    return f"<speak>{body}</speak>"


_ELEVENLABS_VOICE_ID = "NVY0keDZfvfaxrTUzhSK"  # Arkadiusz


async def synthesize_speech(text: str) -> bytes:
    """Call ElevenLabs TTS API; return raw audio/mpeg bytes."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{_ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.content
