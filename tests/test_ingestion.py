"""
Ingestion service tests — TDD, Red → Green → Refactor.
External calls (generate_embedding) are mocked throughout.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.models import Message, Thread, ThreadMessage
from app.models.enums import Channel, Priority, SenderType, Status
from app.services.ingestion import detect_sender_type


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
