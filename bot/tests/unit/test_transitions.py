import pytest

from app.models.enums import BookingStatus
from app.services.transitions import ensure_transition


def test_valid_transition() -> None:
    ensure_transition(BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED)


def test_invalid_transition() -> None:
    with pytest.raises(ValueError):
        ensure_transition(BookingStatus.EXPIRED, BookingStatus.CONFIRMED)
