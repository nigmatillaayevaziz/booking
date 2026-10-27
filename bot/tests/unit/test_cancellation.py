from datetime import UTC, datetime, timedelta

import pytest

from app.services.cancellation import booking_refund_quote, refund_quote


@pytest.mark.parametrize(
    ("hours", "percent"),
    [(25, 100), (24, 70), (7, 70), (6, 30), (2, 30), (0.5, 0)],
)
def test_refund_boundaries(hours: float, percent: int) -> None:
    now = datetime(2026, 10, 26, tzinfo=UTC)
    quote = refund_quote(100_000, now + timedelta(hours=hours), now)
    assert quote.percent == percent
    assert quote.amount == 100_000 * percent // 100


def test_company_cancellation_is_full_refund() -> None:
    now = datetime(2026, 10, 26, tzinfo=UTC)
    assert refund_quote(100_000, now + timedelta(minutes=5), now, company_cancelled=True).amount == 100_000


def test_unpaid_hold_never_creates_a_refund() -> None:
    now = datetime(2026, 10, 26, tzinfo=UTC)
    quote = booking_refund_quote(
        200_000,
        now + timedelta(days=2),
        now,
        payment_received=False,
    )

    assert quote.percent == 0
    assert quote.amount == 0
