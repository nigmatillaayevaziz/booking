from datetime import datetime, time
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    BookingStatus,
    Language,
    NotificationStatus,
    PaymentStatus,
    RoleCode,
    TransportCode,
    TripStatus,
)


def enum_values(enum_class: type[PyEnum]) -> list[str]:
    return [str(member.value) for member in enum_class]


def string_enum(enum_class: type[PyEnum]) -> Enum:
    return Enum(
        enum_class,
        native_enum=False,
        values_callable=enum_values,
        validate_strings=True,
        create_constraint=True,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name_encrypted: Mapped[str] = mapped_column(Text)
    phone_encrypted: Mapped[str | None] = mapped_column(Text)
    phone_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    language: Mapped[Language] = mapped_column(string_enum(Language), default=Language.UZ)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_version: Mapped[str | None] = mapped_column(String(32))
    privacy_version: Mapped[str | None] = mapped_column(String(32))


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[RoleCode] = mapped_column(string_enum(RoleCode), unique=True)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserConsent(Base):
    __tablename__ = "user_consents"
    __table_args__ = (UniqueConstraint("user_id", "terms_version", "privacy_version"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    terms_version: Mapped[str] = mapped_column(String(32))
    privacy_version: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataDeletionRequest(Base, TimestampMixin):
    __tablename__ = "data_deletion_requests"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="requested")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Region(Base, TimestampMixin):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name_uz: Mapped[str] = mapped_column(String(100), unique=True)
    name_ru: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)


class Route(Base, TimestampMixin):
    __tablename__ = "routes"
    __table_args__ = (
        UniqueConstraint("from_region_id", "to_region_id", name="uq_route_direction"),
        CheckConstraint("from_region_id <> to_region_id", name="ck_route_distinct_regions"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    from_region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"))
    to_region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"))
    distance_km: Mapped[int | None] = mapped_column(Integer)
    duration_min: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class RouteFare(Base, TimestampMixin):
    __tablename__ = "route_fares"
    __table_args__ = (
        CheckConstraint("taxi_price IS NULL OR taxi_price > 0", name="ck_fare_taxi_positive"),
        CheckConstraint("bus_price IS NULL OR bus_price > 0", name="ck_fare_bus_positive"),
        CheckConstraint("train_price IS NULL OR train_price > 0", name="ck_fare_train_positive"),
        CheckConstraint(
            "(taxi_price IS NULL OR bus_price IS NULL OR taxi_price > bus_price) AND "
            "(bus_price IS NULL OR train_price IS NULL OR bus_price > train_price) AND "
            "(taxi_price IS NULL OR train_price IS NULL OR taxi_price > train_price)",
            name="ck_fare_transport_order",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), unique=True)
    taxi_price: Mapped[int | None] = mapped_column(BigInteger)
    bus_price: Mapped[int | None] = mapped_column(BigInteger)
    train_price: Mapped[int | None] = mapped_column(BigInteger)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id", ondelete="SET NULL"), index=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"), index=True)
    old_prices: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_prices: Mapped[dict[str, Any]] = mapped_column(JSONB)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransportType(Base, TimestampMixin):
    __tablename__ = "transport_types"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[TransportCode] = mapped_column(string_enum(TransportCode), unique=True)
    name_uz: Mapped[str] = mapped_column(String(50))
    name_ru: Mapped[str] = mapped_column(String(50))
    commission_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    max_passengers_per_booking: Mapped[int] = mapped_column(SmallInteger, default=5)


class Driver(Base, TimestampMixin):
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    license_no_encrypted: Mapped[str] = mapped_column(Text)
    rating_avg: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plate: Mapped[str] = mapped_column(String(20), unique=True)
    model: Mapped[str] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(50))
    seats: Mapped[int] = mapped_column(SmallInteger)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TripTemplate(Base, TimestampMixin):
    __tablename__ = "trip_templates"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"))
    transport_type_id: Mapped[int] = mapped_column(ForeignKey("transport_types.id", ondelete="RESTRICT"))
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    depart_time: Mapped[time] = mapped_column(Time)
    seats: Mapped[int] = mapped_column(SmallInteger)
    price: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Trip(Base, TimestampMixin):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("seats_total > 0", name="ck_trip_total_positive"),
        CheckConstraint("seats_available BETWEEN 0 AND seats_total", name="ck_trip_available_range"),
        CheckConstraint("price > 0", name="ck_trip_price_positive"),
        Index("ix_trip_search", "route_id", "depart_at", "transport_type_id", "status"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="RESTRICT"))
    transport_type_id: Mapped[int] = mapped_column(ForeignKey("transport_types.id", ondelete="RESTRICT"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("trip_templates.id", ondelete="SET NULL"))
    depart_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrive_at_est: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    seats_total: Mapped[int] = mapped_column(SmallInteger)
    seats_available: Mapped[int] = mapped_column(SmallInteger)
    price: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[TripStatus] = mapped_column(
        string_enum(TripStatus), default=TripStatus.SCHEDULED
    )
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"))


class TripDriverAssignment(Base):
    __tablename__ = "trip_driver_assignments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="RESTRICT"), index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("passengers_count BETWEEN 1 AND 5", name="ck_booking_passenger_count"),
        CheckConstraint("total_price >= 0 AND discount_amount >= 0", name="ck_booking_amounts"),
        Index("ix_booking_user_status", "user_id", "status"),
        Index(
            "ix_booking_expiring_holds",
            "hold_expires_at",
            postgresql_where=text("status = 'pending_payment'"),
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"))
    passengers_count: Mapped[int] = mapped_column(SmallInteger)
    unit_price: Mapped[int] = mapped_column(BigInteger)
    total_price: Mapped[int] = mapped_column(BigInteger)
    discount_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    commission_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    commission_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[BookingStatus] = mapped_column(
        string_enum(BookingStatus), default=BookingStatus.PENDING_PAYMENT
    )
    pickup_address_encrypted: Mapped[str | None] = mapped_column(Text)
    pickup_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    pickup_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    note_encrypted: Mapped[str | None] = mapped_column(Text)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    refund_percent: Mapped[int | None] = mapped_column(SmallInteger)
    refund_amount: Mapped[int | None] = mapped_column(BigInteger)
    promo_code_id: Mapped[int | None] = mapped_column(BigInteger)


class BookingPassenger(Base, TimestampMixin):
    __tablename__ = "booking_passengers"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    full_name_encrypted: Mapped[str] = mapped_column(Text)
    seat_no: Mapped[str | None] = mapped_column(String(20))


class BookingEvent(Base):
    __tablename__ = "booking_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event: Mapped[str] = mapped_column(String(80))
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str | None] = mapped_column(String(40))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_payment_provider_external"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(255))
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[PaymentStatus] = mapped_column(string_enum(PaymentStatus))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[PaymentStatus] = mapped_column(string_enum(PaymentStatus))
    reason: Mapped[str] = mapped_column(String(255))


class Rating(Base, TimestampMixin):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_rating_booking"),
        CheckConstraint("stars BETWEEN 1 AND 5", name="ck_rating_stars"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="RESTRICT"))
    stars: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (Index("ix_outbox_due", "status", "scheduled_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deduplication_key: Mapped[str] = mapped_column(String(255), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[NotificationStatus] = mapped_column(
        string_enum(NotificationStatus), default=NotificationStatus.PENDING
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class FunnelEvent(Base):
    __tablename__ = "funnel_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[str] = mapped_column(String(50))
    event: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
