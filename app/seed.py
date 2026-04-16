"""
Seed script — loads data.csv into the database.

Usage:
    uv run python -m app.seed            # seed (no-op if data already present)
    uv run python -m app.seed --force    # wipe all data and reseed
"""

import asyncio
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select, text

from app.database import AsyncSessionLocal
from app.models import (
    AdminFeedback,
    AgentDecision,
    Message,
    OutboundReply,
    Thread,
    ThreadMessage,
    VoiceSession,
)
from app.services.ingestion import ingest_message

# ---------------------------------------------------------------------------
# CSV location
# ---------------------------------------------------------------------------

CSV_PATH = Path(__file__).parent.parent / "data.csv"

# ---------------------------------------------------------------------------
# Timestamp spread — 16 messages over 5 days, oldest first
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)

# Assign a received_at for each CSV row (index 0-based, row ids 1-16)
# Spread: days ago 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 1, 1, 1, 0, 0
_DAYS_AGO = [5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 1, 1, 1, 0, 0, 0]
_HOUR_OFFSETS = [9, 14, 8, 11, 16, 10, 13, 17, 9, 15, 11, 14, 18, 9, 13, 17]


def _timestamp(index: int) -> datetime:
    return (_NOW - timedelta(days=_DAYS_AGO[index])).replace(
        hour=_HOUR_OFFSETS[index], minute=0, second=0, microsecond=0
    )


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _parse_rows() -> list[dict]:
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            rows.append(row)
    return rows


def _build_kwargs(row: dict, index: int) -> dict:
    kanal = row["kanal"].strip()
    channel_map = {"Email": "email", "SMS": "sms", "Voicemail": "voicemail"}
    channel = channel_map[kanal]

    raw_content = row["tresc"].strip()
    sender_ref = row["od"].strip()

    subject_raw = row["temat"].strip()
    subject = None if subject_raw in ("—", "-", "") else subject_raw

    transcription = None
    transcription_confidence = None
    if channel == "voicemail":
        transcription = raw_content
        transcription_confidence = 0.72  # from uwagi: ~72%

    return dict(
        channel=channel,
        raw_content=raw_content,
        sender_ref=sender_ref,
        subject=subject,
        received_at=_timestamp(index),
        transcription=transcription,
        transcription_confidence=transcription_confidence,
    )


# ---------------------------------------------------------------------------
# Wipe helper
# ---------------------------------------------------------------------------

async def _wipe(session) -> None:
    # Delete in dependency order (children before parents)
    for model in (
        AdminFeedback,
        AgentDecision,
        OutboundReply,
        VoiceSession,
        ThreadMessage,
        Message,
        Thread,
    ):
        await session.execute(delete(model))
    await session.flush()


# ---------------------------------------------------------------------------
# Main seed
# ---------------------------------------------------------------------------

async def seed(force: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count(Message.id)))
        if count and count > 0:
            if not force:
                print(f"DB already has {count} message(s). Use --force to reseed.")
                return
            print(f"--force: wiping {count} existing message(s)...")
            await _wipe(session)

        rows = _parse_rows()
        print(f"Seeding {len(rows)} messages from {CSV_PATH.name}...")

        thread_ids: set = set()
        for i, row in enumerate(rows):
            kwargs = _build_kwargs(row, i)
            _, thread = await ingest_message(session, **kwargs)
            thread_ids.add(thread.id)
            print(f"  [{i + 1:02d}] {kwargs['channel']:<10} {kwargs['sender_ref']:<35} → thread {thread.id}")

        await session.commit()

        # --- thread summary ---
        print(f"\nDone. Seeded {len(rows)} messages across {len(thread_ids)} thread(s).")
        print("\nThread summary:")
        result = await session.execute(
            text("""
                SELECT t.id, array_agg(m.sender_ref ORDER BY m.received_at) AS senders
                FROM threads t
                JOIN thread_messages tm ON tm.thread_id = t.id
                JOIN messages m ON m.id = tm.message_id
                GROUP BY t.id
                ORDER BY MIN(m.received_at)
            """)
        )
        for row in result.fetchall():
            senders = row.senders
            if len(senders) > 1:
                print(f"  {str(row.id)[:8]}...  {len(senders)} msgs  {senders}")
            else:
                print(f"  {str(row.id)[:8]}...  1 msg   {senders[0]}")


if __name__ == "__main__":
    asyncio.run(seed(force="--force" in sys.argv))
