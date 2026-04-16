from __future__ import annotations

import logging
import uuid

from app.database import AsyncSessionLocal
from app.services.agent import run_agent

logger = logging.getLogger(__name__)


async def run_agent_background(thread_id: uuid.UUID) -> None:
    """Background task wrapper.

    Creates its own DB session, calls run_agent(), and swallows any exceptions
    so that the originating webhook 202 response is never affected by agent errors.
    """
    logger.info("agent_task_started", extra={
        "event": "agent_task_started",
        "thread_id": str(thread_id),
    })
    try:
        async with AsyncSessionLocal() as session:
            decision = await run_agent(thread_id, session)
        logger.info("agent_task_completed", extra={
            "event": "agent_task_completed",
            "thread_id": str(thread_id),
            "decision_id": str(decision.id),
            "action": decision.action.value,
        })
    except Exception:
        logger.exception("agent_task_failed", extra={
            "event": "agent_task_failed",
            "thread_id": str(thread_id),
        })
