"""
Ingestion service tests — TDD, Red → Green → Refactor.
External calls (generate_embedding) are mocked throughout.
"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.models import Message, Thread, ThreadMessage
from app.models.enums import Channel, Priority, SenderType, Status
from app.services.ingestion import detect_sender_type, find_or_create_thread, ingest_message


FAKE_EMBEDDING = [0.42] * 1536


@pytest.fixture
def session(db_session):
    return db_session()


# ---------------------------------------------------------------------------
# Step 2 — detect_sender_type
# ---------------------------------------------------------------------------


def test_board_detected_by_zarzad_prefix():
    assert detect_sender_type("zarzad@wspolnota-mokotow.pl") == SenderType.board


def test_board_detected_by_board_keyword():
    assert detect_sender_type("board@example.com") == SenderType.board


def test_supplier_detected_by_domain():
    assert detect_sender_type("biuro@bud-serwis.pl") == SenderType.supplier


def test_resident_for_personal_gmail():
    assert detect_sender_type("jan.kowalski@gmail.com") == SenderType.resident


def test_resident_for_wp_pl():
    assert detect_sender_type("m.wisniewska@wp.pl") == SenderType.resident


def test_resident_for_phone_number():
    assert detect_sender_type("+48601234567") == SenderType.resident


def test_resident_for_phone_with_spaces():
    assert detect_sender_type("+48 601 234 567") == SenderType.resident


def test_unknown_for_empty_string():
    assert detect_sender_type("") == SenderType.unknown


# ---------------------------------------------------------------------------
# Step 4 — find_or_create_thread
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_or_create_thread_creates_new_when_no_messages(session):
    async with session as s:
        vec = [0.1] * 1536
        thread = await find_or_create_thread(s, sender_ref="alice@gmail.com", embedding=vec)
        assert thread.id is not None
        assert thread.status == Status.new
        assert thread.priority == Priority.low


@pytest.mark.asyncio
async def test_find_or_create_thread_groups_similar_message(session):
    """Near-identical vectors from same sender → same thread."""
    base_vec = [0.5] * 1536
    # Very close — cosine distance << 0.25
    similar_vec = [0.5] * 1534 + [0.5001, 0.5001]

    async with session as s:
        existing_msg = Message(
            channel=Channel.email,
            raw_content="Heater broken",
            sender_ref="alice@gmail.com",
            sender_type=SenderType.resident,
            embedding=base_vec,
        )
        existing_thread = Thread(priority=Priority.low, status=Status.new)
        s.add_all([existing_msg, existing_thread])
        await s.flush()
        s.add(ThreadMessage(thread_id=existing_thread.id, message_id=existing_msg.id))
        await s.flush()

        thread = await find_or_create_thread(
            s, sender_ref="alice@gmail.com", embedding=similar_vec
        )
        assert thread.id == existing_thread.id


@pytest.mark.asyncio
async def test_find_or_create_thread_creates_new_for_dissimilar_topic(session):
    """Same sender, orthogonal vectors (distance=1.0) → new thread."""
    heater_vec = [1.0] + [0.0] * 1535
    parking_vec = [0.0, 1.0] + [0.0] * 1534

    async with session as s:
        existing_msg = Message(
            channel=Channel.sms,
            raw_content="Heater broken",
            sender_ref="+48601234567",
            sender_type=SenderType.resident,
            embedding=heater_vec,
        )
        existing_thread = Thread(priority=Priority.low, status=Status.new)
        s.add_all([existing_msg, existing_thread])
        await s.flush()
        s.add(ThreadMessage(thread_id=existing_thread.id, message_id=existing_msg.id))
        await s.flush()

        thread = await find_or_create_thread(
            s, sender_ref="+48601234567", embedding=parking_vec
        )
        assert thread.id != existing_thread.id


@pytest.mark.asyncio
async def test_find_or_create_thread_ignores_different_sender(session):
    """Identical vectors but different sender_ref → new thread."""
    vec = [0.5] * 1536

    async with session as s:
        existing_msg = Message(
            channel=Channel.email,
            raw_content="Heater broken",
            sender_ref="bob@gmail.com",
            sender_type=SenderType.resident,
            embedding=vec,
        )
        existing_thread = Thread(priority=Priority.low, status=Status.new)
        s.add_all([existing_msg, existing_thread])
        await s.flush()
        s.add(ThreadMessage(thread_id=existing_thread.id, message_id=existing_msg.id))
        await s.flush()

        thread = await find_or_create_thread(
            s, sender_ref="alice@gmail.com", embedding=vec
        )
        assert thread.id != existing_thread.id
