from __future__ import annotations

import logging
import uuid

import anthropic
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import AgentDecision, Message, Thread, ThreadMessage
from app.models.enums import Action, Status
from app.services.feedback import format_few_shot_examples, retrieve_similar_corrections
from app.services.tools import (
    TOOLS,
    classify_and_set_category,
    draft_reply,
    escalate,
    group_messages,
    mark_no_action,
    search_similar_threads,
)

logger = logging.getLogger(__name__)

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

_STATIC_SYSTEM_PROMPT = """You are an AI property management assistant for a residential building in Warsaw, Poland.
You receive messages from residents (email/SMS/voicemail), suppliers, and the building board.
Your job is to classify incoming messages, group related threads, draft replies, or escalate urgent issues.
Your reasoning and decision rationale must always be in Polish.
When drafting replies, respond in the same language as the resident's message.
When drafting email or SMS replies, always sign them with "Administracja" on a new line at the end.
Property context: 40-60 messages/day, mix of Polish and English residents.
Available actions: classify_and_set_category, group_messages, draft_reply, escalate, search_similar_threads, mark_no_action.

Category names in Polish: konserwacja, płatność, skarga na hałas, najem, ogólne, dostawca, inne.
Priority names in Polish: niski, średni, wysoki, pilny.
Always use Polish names when explaining actions in your reasoning.
Do not use emoticons or emoji in your responses.

## Escalation rules — apply automatically, no admin input needed

1. **Repeated follow-up**: if the thread contains 2 or more messages from the same sender about the same issue, or if any message explicitly states it is a repeated attempt ("piszę po raz", "kolejny raz", "brak odpowiedzi", "third time", "again"), call escalate() immediately and set priority to urgent.
2. **Safety risk**: any mention of flooding, electrical hazard, fire, gas, or structural danger — escalate immediately regardless of message count.
3. **Legal threat**: any message mentioning legal action, regulatory body, or formal complaint ("zgłoszę do nadzoru", "sprawa do sądu", "zawiadomienie") — escalate and set priority to urgent.

When escalating, include the specific reason in your rationale (e.g. "trzecia wiadomość od tego samego nadawcy w tej samej sprawie").

When you finish, provide a concise summary in Polish of ONLY the actions you actually took (tools you called).
Do not mention any actions you did not perform.
Use the tools to take action, then stop when you have completed all necessary actions."""

_TOOL_DISPATCH = {
    "classify_and_set_category": classify_and_set_category,
    "group_messages": group_messages,
    "draft_reply": draft_reply,
    "escalate": escalate,
    "search_similar_threads": search_similar_threads,
    "mark_no_action": mark_no_action,
}

def _determine_final_action(tools_called: list[str]) -> Action:
    """Infer the agent's final action from which tools fired during the loop."""
    if "escalate" in tools_called:
        return Action.escalate
    if "draft_reply" in tools_called:
        return Action.draft_reply
    if "mark_no_action" in tools_called:
        return Action.no_action
    return Action.group_only


async def assemble_system_prompt(
    thread_id: uuid.UUID,
    session: AsyncSession,
) -> list[dict]:
    """Return a list of Anthropic content blocks for the system parameter.

    Block 0 — static role + property context (cache_control: ephemeral).
    Block 1 — dynamic few-shot corrections (no cache_control).
    """
    corrections = await retrieve_similar_corrections(
        session, thread_id, top_n=5
    )
    few_shot_text = format_few_shot_examples(corrections)
    dynamic_text = few_shot_text if few_shot_text else "No past corrections available."

    return [
        {
            "type": "text",
            "text": _STATIC_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": dynamic_text,
        },
    ]


async def run_agent(thread_id: uuid.UUID, session: AsyncSession) -> AgentDecision:
    """Run the agentic loop for a thread and persist an AgentDecision."""
    # Fetch thread with its messages
    result = await session.execute(
        select(Thread)
        .options(
            selectinload(Thread.messages)
        )
        .where(Thread.id == thread_id)
    )
    thread = result.scalar_one()

    # Fetch messages for this thread (via junction table) ordered by received_at
    msg_result = await session.execute(
        select(Message)
        .join(ThreadMessage, ThreadMessage.message_id == Message.id)
        .where(ThreadMessage.thread_id == thread_id)
        .order_by(Message.received_at)
    )
    messages = list(msg_result.scalars().all())

    # Retrieve few-shot corrections before creating the decision (need their IDs)
    corrections = await retrieve_similar_corrections(
        session, thread_id, top_n=5
    )
    few_shot_ids = [c.id for c in corrections]
    few_shot_text = format_few_shot_examples(corrections)
    dynamic_text = few_shot_text if few_shot_text else "No past corrections available."

    system_blocks = [
        {
            "type": "text",
            "text": _STATIC_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": dynamic_text,
        },
    ]

    # Mark any previous decisions as not current
    await session.execute(
        update(AgentDecision)
        .where(AgentDecision.thread_id == thread_id, AgentDecision.is_current == True)  # noqa: E712
        .values(is_current=False)
    )

    # Create the in-progress decision row (tools may mutate it during the loop)
    decision = AgentDecision(
        thread_id=thread_id,
        action=Action.no_action,
        rationale="",
        model_id=settings.MODEL_ID,
        few_shot_ids=few_shot_ids,
        is_current=True,
    )
    session.add(decision)
    await session.flush()

    logger.info("agent_run_started", extra={
        "event": "agent_run_started",
        "thread_id": str(thread_id),
        "message_count": len(messages),
        "few_shot_count": len(few_shot_ids),
    })

    # Build the initial user message
    thread_header = f"Thread ID: {thread_id}\nMessages ({len(messages)} total):\n"
    message_parts = []
    for msg in messages:
        content = msg.transcription or msg.raw_content
        message_parts.append(
            f"[Message ID: {msg.id}] [{msg.channel.value} from {msg.sender_ref}]: {content}"
        )
    user_content = thread_header + "\n".join(message_parts)

    # Agentic loop
    conversation: list[dict] = [{"role": "user", "content": user_content}]
    tools_called: list[str] = []
    total_input = total_output = total_cache_read = total_cache_create = 0
    turn_number = 0

    while True:
        response = await anthropic_client.messages.create(
            model=settings.MODEL_ID,
            max_tokens=2048,
            system=system_blocks,
            tools=TOOLS,
            messages=conversation,
        )

        turn_number += 1
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens
        total_cache_read += getattr(response.usage, "cache_read_input_tokens", 0) or 0
        total_cache_create += getattr(response.usage, "cache_creation_input_tokens", 0) or 0

        logger.debug("llm_turn", extra={
            "event": "llm_turn",
            "thread_id": str(thread_id),
            "turn": turn_number,
            "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        })

        if response.stop_reason == "end_turn":
            # Extract rationale from the final text block if present
            rationale = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    rationale = block.text
                    break
            decision.rationale = rationale
            break

        # Process tool_use blocks
        tool_results = []
        for block in response.content:
            if not (hasattr(block, "type") and block.type == "tool_use"):
                continue

            tool_name = block.name
            tool_input = block.input
            tools_called.append(tool_name)

            logger.info("tool_dispatched", extra={
                "event": "tool_dispatched",
                "thread_id": str(thread_id),
                "tool_name": tool_name,
            })

            try:
                handler = _TOOL_DISPATCH[tool_name]
                tool_result = await handler(session, thread_id, **tool_input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(tool_result),
                })
            except Exception as exc:
                logger.error("tool_failed", extra={
                    "event": "tool_failed",
                    "thread_id": str(thread_id),
                    "tool_name": tool_name,
                    "error": str(exc),
                })
                await session.rollback()
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": str(exc),
                })

        # Append assistant turn + tool results to conversation
        conversation.append({"role": "assistant", "content": response.content})
        conversation.append({"role": "user", "content": tool_results})

    # Persist token usage
    decision.input_tokens = total_input
    decision.output_tokens = total_output
    decision.cache_read_tokens = total_cache_read
    decision.cache_creation_tokens = total_cache_create

    # Determine final action from which tools fired
    decision.action = _determine_final_action(tools_called)

    # Update thread status
    thread.status = Status.pending_review

    await session.commit()

    logger.info("agent_run_completed", extra={
        "event": "agent_run_completed",
        "thread_id": str(thread_id),
        "decision_id": str(decision.id),
        "action": decision.action.value,
        "turns": turn_number,
        "tools_called": tools_called,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read_tokens": total_cache_read,
        "total_cache_creation_tokens": total_cache_create,
    })

    return decision
