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


# ---------------------------------------------------------------------------
# Step 5 — ingest_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_message_persists_message_and_thread(session):
    async with session as s:
        with patch(
            "app.services.ingestion._embeddings.generate_embedding",
            new=AsyncMock(return_value=FAKE_EMBEDDING),
        ):
            msg, thread = await ingest_message(
                session=s,
                channel="email",
                raw_content="The gate is broken",
                subject="Broken gate",
                sender_ref="jan@gmail.com",
            )
            await s.commit()

        result = await s.execute(select(Message).where(Message.id == msg.id))
        saved = result.scalar_one()
        assert saved.raw_content == "The gate is broken"
        assert saved.sender_type == SenderType.resident
        assert saved.subject == "Broken gate"

        tm_result = await s.execute(
            select(ThreadMessage).where(ThreadMessage.message_id == msg.id)
        )
        tm = tm_result.scalar_one()
        assert tm.thread_id == thread.id


@pytest.mark.asyncio
async def test_ingest_message_detects_board_sender(session):
    async with session as s:
        with patch(
            "app.services.ingestion._embeddings.generate_embedding",
            new=AsyncMock(return_value=FAKE_EMBEDDING),
        ):
            msg, _ = await ingest_message(
                session=s,
                channel="email",
                raw_content="Board decision on roof repair",
                subject="Roof decision",
                sender_ref="zarzad@wspolnota-mokotow.pl",
            )
            await s.commit()
    assert msg.sender_type == SenderType.board


@pytest.mark.asyncio
async def test_ingest_voicemail_without_transcription_embeds_raw_content(session):
    async with session as s:
        with patch(
            "app.services.ingestion._embeddings.generate_embedding",
            new=AsyncMock(return_value=FAKE_EMBEDDING),
        ) as mock_embed:
            msg, _ = await ingest_message(
                session=s,
                channel="voicemail",
                raw_content="https://s3.example/call.mp3",
                sender_ref="+48888100200",
            )
            await s.commit()
        mock_embed.assert_called_once_with("https://s3.example/call.mp3")
        assert msg.transcription is None


@pytest.mark.asyncio
async def test_ingest_voicemail_with_transcription_embeds_transcription(session):
    async with session as s:
        with patch(
            "app.services.ingestion._embeddings.generate_embedding",
            new=AsyncMock(return_value=FAKE_EMBEDDING),
        ) as mock_embed:
            await ingest_message(
                session=s,
                channel="voicemail",
                raw_content="https://s3.example/call.mp3",
                sender_ref="+48888100200",
                transcription="Water in basement",
                transcription_confidence=0.72,
            )
        mock_embed.assert_called_once_with("Water in basement")


# ---------------------------------------------------------------------------
# Step 7 — End-to-end thread grouping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_follow_up_message_grouped_into_same_thread(session):
    """
    First message → creates thread.
    Follow-up from same sender on same topic → joins thread.
    Unrelated message from same sender → new thread.
    """
    gate_vec = [1.0] + [0.0] * 1535
    gate_vec2 = [0.999] + [0.001 / 1535] * 1535   # very close
    park_vec = [0.0, 1.0] + [0.0] * 1534           # orthogonal

    async with session as s:
        with patch(
            "app.services.ingestion._embeddings.generate_embedding",
            new=AsyncMock(side_effect=[gate_vec, gate_vec2, park_vec]),
        ):
            msg1, thread1 = await ingest_message(
                s, channel="email", raw_content="Gate broken first time",
                sender_ref="jan@gmail.com",
            )
            await s.flush()

            msg2, thread2 = await ingest_message(
                s, channel="email", raw_content="Gate still broken",
                sender_ref="jan@gmail.com",
            )
            await s.flush()

            msg3, thread3 = await ingest_message(
                s, channel="email", raw_content="Where is my parking spot?",
                sender_ref="jan@gmail.com",
            )
            await s.commit()

    assert thread1.id == thread2.id, "Follow-up should join existing thread"
    assert thread3.id != thread1.id, "Unrelated topic should create new thread"


@pytest.mark.asyncio
async def test_supplier_and_resident_never_grouped(session):
    """Supplier invoice should not merge with a resident thread even if vectors are identical."""
    vec = [0.5] * 1536

    async with session as s:
        with patch(
            "app.services.ingestion._embeddings.generate_embedding",
            new=AsyncMock(return_value=vec),
        ):
            msg_resident, t_resident = await ingest_message(
                s, channel="email", raw_content="Gate broken",
                sender_ref="jan@gmail.com",
            )
            await s.flush()

            msg_supplier, t_supplier = await ingest_message(
                s, channel="email",
                raw_content="Invoice FS/2024/0892 for gas inspection",
                sender_ref="biuro@bud-serwis.pl",
            )
            await s.commit()

    assert msg_resident.sender_type == SenderType.resident
    assert msg_supplier.sender_type == SenderType.supplier
    assert t_supplier.id != t_resident.id
