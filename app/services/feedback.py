from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminFeedback, Message, ThreadMessage
from app.models.enums import FeedbackType


async def retrieve_similar_corrections(
    session: AsyncSession,
    thread_id: uuid.UUID,
    top_n: int = 5,
) -> list[AdminFeedback]:
    """Return the top-N most similar corrected/overridden feedback records.

    Uses the first message in the thread as the query embedding. Returns an
    empty list if no messages have embeddings or if no matching feedback exists.
    """
    # Find a representative embedding for the thread (first non-null message embedding)
    row = await session.execute(
        select(Message.embedding)
        .join(ThreadMessage, ThreadMessage.message_id == Message.id)
        .where(
            ThreadMessage.thread_id == thread_id,
            Message.embedding.isnot(None),
        )
        .limit(1)
    )
    embedding = row.scalar_one_or_none()
    if embedding is None:
        return []

    result = await session.execute(
        select(AdminFeedback)
        .where(
            AdminFeedback.feedback_type.in_(
                [FeedbackType.corrected, FeedbackType.overridden]
            ),
            AdminFeedback.embedding.isnot(None),
        )
        .order_by(AdminFeedback.embedding.op("<=>")(embedding))
        .limit(top_n)
    )
    return list(result.scalars().all())


def format_few_shot_examples(corrections: list[AdminFeedback]) -> str:
    """Format a list of AdminFeedback records as a natural-language block for prompt injection."""
    if not corrections:
        return ""

    lines: list[str] = []
    for i, fb in enumerate(corrections, start=1):
        lines.append(f"Example {i}:")
        if fb.correction_note:
            lines.append(f"  Context: {fb.correction_note}")
        original = fb.original_action.value if hasattr(fb.original_action, "value") else str(fb.original_action)
        lines.append(f"  Original action: {original}")
        if fb.corrected_action is not None:
            corrected = fb.corrected_action.value if hasattr(fb.corrected_action, "value") else str(fb.corrected_action)
            lines.append(f"  Corrected to: {corrected}")
        if fb.corrected_draft:
            lines.append(f"  Draft: {fb.corrected_draft}")
        lines.append("")

    return "\n".join(lines).strip()
