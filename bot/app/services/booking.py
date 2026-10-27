import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import PIICipher
from app.models.entities import (
    AuditLog,
    Booking,
    BookingEvent,
    BookingPassenger,
    NotificationOutbox,
    Payment,
    TransportType,
    Trip,
    User,
)
from app.models.enums import BookingStatus, NotificationStatus, PaymentStatus, TripStatus
from app.services.cancellation import (
    DEFAULT_CANCELLATION_POLICY,
    CancellationPolicy,
    RefundQuote,
    booking_refund_quote,
)
from app.services.pricing import booking_total, commission_amount
from app.services.transitions import ensure_transition


class BookingError(ValueError):
    pass


def booking_number(now: datetime) -> str:
    return f"TB-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"


async def create_hold(
    session: AsyncSession,
    *,
    settings: Settings,
    cipher: PIICipher,
    user_id: int,
    trip_id: int,
    passenger_names: list[str],
    pickup_address: str | None = None,
    pickup_lat: Decimal | None = None,
    pickup_lng: Decimal | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Booking:
    now = now or datetime.now(UTC)
    names = [name.strip() for name in passenger_names if name.strip()]
    if not names or len(names) != len(passenger_names):
        raise BookingError("Har bir yo‘lovchining ismi kiritilishi kerak")

    user_exists = await session.scalar(select(User.id).where(User.id == user_id).with_for_update())
    if user_exists is None:
        raise BookingError("Foydalanuvchi topilmadi")

    active_holds = await session.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.user_id == user_id,
            Booking.status == BookingStatus.PENDING_PAYMENT,
            Booking.hold_expires_at > now,
        )
    )
    if int(active_holds or 0) >= settings.max_active_holds:
        raise BookingError("Bir vaqtda juda ko‘p faol to‘lov kutilyapti")

    trip = await session.scalar(select(Trip).where(Trip.id == trip_id).with_for_update())
    if trip is None or trip.status != TripStatus.SCHEDULED:
        raise BookingError("Reys sotuvda emas")
    if trip.depart_at <= now + timedelta(minutes=settings.booking_cutoff_minutes):
        raise BookingError("Bu reysga band qilish yopilgan")
    if trip.depart_at > now + timedelta(days=settings.booking_horizon_days):
        raise BookingError("Reys ruxsat etilgan muddatdan uzoqda")

    transport = await session.get(TransportType, trip.transport_type_id)
    if transport is None:
        raise BookingError("Transport turi topilmadi")
    passengers = len(names)
    if passengers > transport.max_passengers_per_booking:
        raise BookingError(f"Bu transport uchun maksimum {transport.max_passengers_per_booking} yo‘lovchi")
    if trip.seats_available < passengers:
        raise BookingError(f"Faqat {trip.seats_available} ta joy qoldi")

    total = booking_total(trip.price, passengers)
    commission = commission_amount(total, transport.commission_pct)
    trip.seats_available -= passengers
    booking = Booking(
        number=booking_number(now),
        user_id=user_id,
        trip_id=trip.id,
        passengers_count=passengers,
        unit_price=trip.price,
        total_price=total,
        discount_amount=0,
        commission_pct=transport.commission_pct,
        commission_amount=commission,
        status=BookingStatus.PENDING_PAYMENT,
        pickup_address_encrypted=cipher.encrypt(pickup_address),
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        note_encrypted=cipher.encrypt(note),
        hold_expires_at=now + timedelta(minutes=settings.hold_minutes),
    )
    session.add(booking)
    await session.flush()
    session.add_all(
        BookingPassenger(booking_id=booking.id, full_name_encrypted=cipher.encrypt(name)) for name in names
    )
    session.add(
        BookingEvent(
            booking_id=booking.id,
            actor_id=user_id,
            event="booking.hold_created",
            from_status=None,
            to_status=BookingStatus.PENDING_PAYMENT.value,
            payload={"trip_id": trip.id, "passengers_count": passengers},
        )
    )
    reminder_delay = min(10, max(1, settings.hold_minutes - 5))
    session.add(
        NotificationOutbox(
            deduplication_key=f"booking:{booking.id}:payment_reminder",
            user_id=user_id,
            type="payment_reminder",
            payload={"booking_id": booking.id, "number": booking.number},
            status=NotificationStatus.PENDING,
            scheduled_at=now + timedelta(minutes=reminder_delay),
        )
    )
    return booking


async def release_expired_holds(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    batch_size: int = 100,
) -> list[int]:
    now = now or datetime.now(UTC)
    result = await session.scalars(
        select(Booking)
        .where(
            Booking.status == BookingStatus.PENDING_PAYMENT,
            Booking.hold_expires_at < now,
        )
        .order_by(Booking.trip_id, Booking.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    bookings = list(result)
    released: list[int] = []
    for booking in bookings:
        trip = await session.scalar(select(Trip).where(Trip.id == booking.trip_id).with_for_update())
        if trip is None:
            continue
        ensure_transition(booking.status, BookingStatus.EXPIRED)
        previous_status = booking.status
        booking.status = BookingStatus.EXPIRED
        trip.seats_available += booking.passengers_count
        session.add(
            NotificationOutbox(
                deduplication_key=f"booking:{booking.id}:expired",
                user_id=booking.user_id,
                type="hold_expired",
                payload={"booking_id": booking.id, "number": booking.number},
                status=NotificationStatus.PENDING,
                scheduled_at=now,
            )
        )
        session.add(
            BookingEvent(
                booking_id=booking.id,
                actor_id=None,
                event="booking.hold_expired",
                from_status=previous_status.value,
                to_status=BookingStatus.EXPIRED.value,
                payload=None,
            )
        )
        released.append(booking.id)
    return released


async def confirm_manual_payment(
    session: AsyncSession,
    *,
    booking_id: int,
    actor_user_id: int,
    external_id: str,
    request_id: str,
    now: datetime | None = None,
) -> Booking:
    now = now or datetime.now(UTC)
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None:
        raise BookingError("Buyurtma topilmadi")
    if booking.status == BookingStatus.CONFIRMED:
        return booking
    if booking.status != BookingStatus.PENDING_PAYMENT or not booking.hold_expires_at:
        raise BookingError("Buyurtma to‘lov kutmayapti")
    if booking.hold_expires_at < now:
        raise BookingError("Hold muddati tugagan")
    ensure_transition(booking.status, BookingStatus.CONFIRMED)
    previous_status = booking.status
    booking.status = BookingStatus.CONFIRMED
    booking.confirmed_at = now
    session.add(
        Payment(
            booking_id=booking.id,
            provider="manual",
            external_id=external_id,
            amount=booking.total_price,
            status=PaymentStatus.PAID,
            raw_payload={"confirmed_by": actor_user_id},
            paid_at=now,
        )
    )
    session.add(
        NotificationOutbox(
            deduplication_key=f"booking:{booking.id}:confirmed",
            user_id=booking.user_id,
            type="booking_confirmed",
            payload={"booking_id": booking.id, "number": booking.number},
            status=NotificationStatus.PENDING,
            scheduled_at=now,
        )
    )
    session.add_all(
        [
            BookingEvent(
                booking_id=booking.id,
                actor_id=actor_user_id,
                event="booking.payment_confirmed",
                from_status=previous_status.value,
                to_status=BookingStatus.CONFIRMED.value,
                payload={"provider": "manual", "external_id": external_id},
            ),
            AuditLog(
                actor_id=actor_user_id,
                action="booking.manual_payment_confirmed",
                entity="bookings",
                entity_id=str(booking.id),
                before={"status": previous_status.value},
                after={"status": BookingStatus.CONFIRMED.value, "amount": booking.total_price},
                request_id=request_id,
            ),
        ]
    )
    return booking


async def cancel_booking(
    session: AsyncSession,
    *,
    booking_id: int,
    requested_by_user_id: int,
    policy: CancellationPolicy | None = None,
    company_cancelled: bool = False,
    now: datetime | None = None,
) -> tuple[Booking, RefundQuote]:
    now = now or datetime.now(UTC)
    policy = policy or DEFAULT_CANCELLATION_POLICY
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None:
        raise BookingError("Buyurtma topilmadi")
    if not company_cancelled and booking.user_id != requested_by_user_id:
        raise BookingError("Bu buyurtmani bekor qilishga ruxsat yo‘q")
    if booking.status not in {BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED}:
        raise BookingError("Buyurtmani bu holatda bekor qilib bo‘lmaydi")

    trip = await session.scalar(select(Trip).where(Trip.id == booking.trip_id).with_for_update())
    if trip is None:
        raise BookingError("Reys topilmadi")
    previous_status = booking.status
    quote = booking_refund_quote(
        booking.total_price,
        trip.depart_at,
        now,
        payment_received=booking.status == BookingStatus.CONFIRMED,
        policy=policy,
        company_cancelled=company_cancelled,
    )
    trip.seats_available += booking.passengers_count
    booking.cancelled_at = now
    booking.cancel_reason = "company_cancelled" if company_cancelled else "passenger_cancelled"
    booking.refund_percent = quote.percent
    booking.refund_amount = quote.amount
    target = (
        BookingStatus.REFUND_PENDING
        if booking.status == BookingStatus.CONFIRMED and quote.amount > 0
        else BookingStatus.CANCELLED
    )
    ensure_transition(booking.status, target)
    booking.status = target
    session.add(
        NotificationOutbox(
            deduplication_key=f"booking:{booking.id}:cancelled:{target.value}",
            user_id=booking.user_id,
            type="booking_cancelled",
            payload={
                "booking_id": booking.id,
                "number": booking.number,
                "refund_percent": quote.percent,
                "refund_amount": quote.amount,
            },
            status=NotificationStatus.PENDING,
            scheduled_at=now,
        )
    )
    session.add(
        BookingEvent(
            booking_id=booking.id,
            actor_id=requested_by_user_id,
            event="booking.cancelled",
            from_status=previous_status.value,
            to_status=target.value,
            payload={
                "company_cancelled": company_cancelled,
                "refund_percent": quote.percent,
                "refund_amount": quote.amount,
            },
        )
    )
    return booking, quote
