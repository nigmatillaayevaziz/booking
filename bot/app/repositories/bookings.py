from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.entities import Booking, BookingPassenger, Region, Route, TransportType, Trip
from app.models.enums import BookingStatus

type SummaryRow = tuple[int, str, BookingStatus, int, int, datetime, str, str, str]


@dataclass(frozen=True, slots=True)
class BookingSummary:
    id: int
    number: str
    status: BookingStatus
    total_price: int
    passengers_count: int
    depart_at: datetime
    from_region: str
    to_region: str
    transport: str


class BookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _summary_query(self, language: str):  # type: ignore[no-untyped-def]
        origin = aliased(Region)
        destination = aliased(Region)
        origin_name = origin.name_ru if language == "ru" else origin.name_uz
        destination_name = destination.name_ru if language == "ru" else destination.name_uz
        transport_name = TransportType.name_ru if language == "ru" else TransportType.name_uz
        return (
            select(
                Booking.id,
                Booking.number,
                Booking.status,
                Booking.total_price,
                Booking.passengers_count,
                Trip.depart_at,
                origin_name,
                destination_name,
                transport_name,
            )
            .join(Trip, Trip.id == Booking.trip_id)
            .join(Route, Route.id == Trip.route_id)
            .join(origin, origin.id == Route.from_region_id)
            .join(destination, destination.id == Route.to_region_id)
            .join(TransportType, TransportType.id == Trip.transport_type_id)
        )

    @staticmethod
    def _to_summary(row: SummaryRow) -> BookingSummary:
        return BookingSummary(
            id=row[0],
            number=row[1],
            status=row[2],
            total_price=row[3],
            passengers_count=row[4],
            depart_at=row[5],
            from_region=row[6],
            to_region=row[7],
            transport=row[8],
        )

    async def list_for_user(
        self,
        user_id: int,
        language: str,
        statuses: set[BookingStatus],
        *,
        limit: int = 10,
    ) -> list[BookingSummary]:
        result = await self.session.execute(
            self._summary_query(language)
            .where(Booking.user_id == user_id, Booking.status.in_(statuses))
            .order_by(Trip.depart_at.desc())
            .limit(limit)
        )
        return [self._to_summary(cast(SummaryRow, tuple(row))) for row in result]

    async def summary_for_user(
        self, booking_id: int, user_id: int, language: str
    ) -> BookingSummary | None:
        row = (
            await self.session.execute(
                self._summary_query(language).where(
                    Booking.id == booking_id,
                    Booking.user_id == user_id,
                )
            )
        ).first()
        return self._to_summary(cast(SummaryRow, tuple(row))) if row else None

    async def passenger_names(self, booking_id: int) -> list[str]:
        rows = await self.session.scalars(
            select(BookingPassenger.full_name_encrypted)
            .where(BookingPassenger.booking_id == booking_id)
            .order_by(BookingPassenger.id)
        )
        return list(rows)
