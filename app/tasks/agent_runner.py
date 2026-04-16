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
    try:
        async with AsyncSessionLocal() as session:
            await run_agent(thread_id, session)
    except Exception:
        logger.exception("Background agent run failed for thread %s", thread_id)
