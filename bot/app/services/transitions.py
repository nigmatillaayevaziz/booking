from app.models.enums import BookingStatus

ALLOWED_BOOKING_TRANSITIONS: dict[BookingStatus, frozenset[BookingStatus]] = {
    BookingStatus.PENDING_PAYMENT: frozenset(
        {BookingStatus.CONFIRMED, BookingStatus.EXPIRED, BookingStatus.CANCELLED}
    ),
    BookingStatus.CONFIRMED: frozenset(
        {
            BookingStatus.COMPLETED,
            BookingStatus.CANCELLED,
            BookingStatus.REFUND_PENDING,
            BookingStatus.NO_SHOW,
        }
    ),
    BookingStatus.CANCELLED: frozenset({BookingStatus.REFUND_PENDING}),
    BookingStatus.REFUND_PENDING: frozenset({BookingStatus.REFUNDED}),
    BookingStatus.COMPLETED: frozenset(),
    BookingStatus.EXPIRED: frozenset(),
    BookingStatus.REFUNDED: frozenset(),
    BookingStatus.NO_SHOW: frozenset(),
}


def ensure_transition(current: BookingStatus, target: BookingStatus) -> None:
    if target not in ALLOWED_BOOKING_TRANSITIONS[current]:
        raise ValueError(f"Booking holatini {current.value} dan {target.value} ga o‘tkazib bo‘lmaydi")
