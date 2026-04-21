from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentDecision, Message, Thread, ThreadMessage
from app.models.enums import Category, Priority, Status

# Polish translations for enum values used in agent responses
POLISH_CATEGORY = {
    "maintenance": "konserwacja",
    "payment": "płatność",
    "noise_complaint": "skarga na hałas",
    "lease": "najem",
    "general": "ogólne",
    "supplier": "dostawca",
    "other": "inne",
}

POLISH_PRIORITY = {
    "low": "niski",
    "medium": "średni",
    "high": "wysoki",
    "urgent": "pilny",
}

TOOLS: list[dict] = [
    {
        "name": "classify_and_set_category",
        "description": (
            "Set the thread's category and priority based on the message content. "
            "Call this once you have determined what kind of issue the thread represents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [c.value for c in Category],
                    "description": "The category that best describes this thread.",
                },
                "priority": {
                    "type": "string",
                    "enum": [p.value for p in Priority],
                    "description": "The urgency level for this thread.",
                },
            },
            "required": ["category", "priority"],
        },
    },
    {
        "name": "group_messages",
        "description": (
            "Add one or more messages into the current thread. "
            "Use this when you identify messages that belong to the same issue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of message UUIDs to add to this thread.",
                },
            },
            "required": ["message_ids"],
        },
    },
    {
        "name": "draft_reply",
        "description": (
            "Write a draft reply to send to the resident. "
            "Reply in the same language the resident used. "
            "Be concise and professional."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_text": {
                    "type": "string",
                    "description": "The full text of the reply to the resident.",
                },
            },
            "required": ["draft_text"],
        },
    },
    {
        "name": "escalate",
        "description": (
            "Mark the thread as escalated and set priority to urgent. "
            "Use this for safety issues, legal threats, or anything requiring immediate human attention."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "search_similar_threads",
        "description": (
            "Search for similar past threads using semantic similarity. "
            "Use this to find how similar issues were resolved before."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A natural language description of what to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "mark_no_action",
        "description": (
            "Record that no action is needed for this thread. "
            "Use this for spam, duplicates, or messages that require no response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rationale": {
                    "type": "string",
                    "description": "Brief explanation of why no action is needed.",
                },
            },
            "required": ["rationale"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def classify_and_set_category(
    session: AsyncSession,
    thread_id: uuid.UUID,
    category: str,
    priority: str,
) -> dict:
    result = await session.execute(select(Thread).where(Thread.id == thread_id))
    thread = result.scalar_one()
    thread.category = Category(category)
    thread.priority = Priority(priority)
    await session.flush()
    return {
        "ok": True,
        "category": POLISH_CATEGORY.get(category, category),
        "priority": POLISH_PRIORITY.get(priority, priority),
    }


async def group_messages(
    session: AsyncSession,
    thread_id: uuid.UUID,
    message_ids: list[str],
) -> dict:
    added = []
    source_thread_ids: set[uuid.UUID] = set()

    for mid_str in message_ids:
        mid = uuid.UUID(mid_str)
        existing = await session.execute(
            select(ThreadMessage).where(
                ThreadMessage.thread_id == thread_id,
                ThreadMessage.message_id == mid,
            )
        )
        if existing.scalar_one_or_none() is None:
            # Find which other threads own this message before adding it here
            source_rows = await session.execute(
                select(ThreadMessage.thread_id).where(
                    ThreadMessage.message_id == mid,
                    ThreadMessage.thread_id != thread_id,
                )
            )
            for row in source_rows:
                source_thread_ids.add(row.thread_id)

            session.add(ThreadMessage(thread_id=thread_id, message_id=mid))
            added.append(mid_str)

    # Mark source threads as resolved — they've been consolidated here
    for src_id in source_thread_ids:
        src_thread = await session.get(Thread, src_id)
        if src_thread is not None and src_thread.status not in (
            Status.resolved, Status.replied
        ):
            src_thread.status = Status.resolved

    await session.flush()
    return {"ok": True, "added": added, "resolved_threads": [str(t) for t in source_thread_ids]}


async def draft_reply(
    session: AsyncSession,
    thread_id: uuid.UUID,
    draft_text: str,
) -> dict:
    result = await session.execute(
        select(AgentDecision).where(
            AgentDecision.thread_id == thread_id,
            AgentDecision.is_current == True,  # noqa: E712
        )
    )
    decision = result.scalar_one()
    decision.draft_reply = draft_text
    await session.flush()
    return {"ok": True, "draft_length": len(draft_text)}


async def escalate(
    session: AsyncSession,
    thread_id: uuid.UUID,
) -> dict:
    result = await session.execute(select(Thread).where(Thread.id == thread_id))
    thread = result.scalar_one()
    thread.status = Status.escalated
    thread.priority = Priority.urgent
    await session.flush()
    return {"ok": True, "status": "eskalowany", "priority": POLISH_PRIORITY["urgent"]}


async def search_similar_threads(
    session: AsyncSession,
    thread_id: uuid.UUID,
    query: str,
) -> dict:
    from app.services import embeddings as _embeddings

    query_embedding = await _embeddings.generate_embedding(query)

    rows = await session.execute(
        select(Message.id, Message.raw_content, Message.sender_ref)
        .where(Message.embedding.isnot(None))
        .order_by(Message.embedding.op("<=>")(query_embedding))
        .limit(5)
    )
    results = [
        {"message_id": str(row.id), "sender_ref": row.sender_ref, "content": row.raw_content[:200]}
        for row in rows
    ]
    return {"similar_threads": results}


async def mark_no_action(
    session: AsyncSession,
    thread_id: uuid.UUID,
    rationale: str,
) -> dict:
    result = await session.execute(select(Thread).where(Thread.id == thread_id))
    thread = result.scalar_one()
    thread.status = Status.resolved
    await session.flush()
    return {"ok": True, "rationale": rationale}
