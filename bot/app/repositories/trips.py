from datetime import UTC, date, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.engine import ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.entities import Region, Route, TransportType, Trip
from app.models.enums import TripStatus


class TripRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def origin_regions(
        self, language: str, *, cutoff_minutes: int, horizon_days: int
    ) -> list[tuple[int, str]]:
        now = datetime.now(UTC)
        name = Region.name_ru if language == "ru" else Region.name_uz
        rows = await self.session.execute(
            select(distinct(Region.id), name)
            .join(Route, Route.from_region_id == Region.id)
            .join(Trip, Trip.route_id == Route.id)
            .where(
                Region.is_active.is_(True),
                Route.is_active.is_(True),
                Trip.status == TripStatus.SCHEDULED,
                Trip.seats_available > 0,
                Trip.depart_at > now + timedelta(minutes=cutoff_minutes),
                Trip.depart_at <= now + timedelta(days=horizon_days),
            )
            .order_by(name)
        )
        return [(row[0], row[1]) for row in rows]

    async def route_id(self, from_region_id: int, to_region_id: int) -> int | None:
        return await self.session.scalar(
            select(Route.id).where(
                Route.from_region_id == from_region_id,
                Route.to_region_id == to_region_id,
                Route.is_active.is_(True),
            )
        )

    async def available_dates(self, route_id: int, cutoff_minutes: int, limit: int = 7) -> list[str]:
        now = datetime.now(UTC)
        rows: ScalarResult[date] = await self.session.scalars(
            select(func.date(Trip.depart_at))
            .where(
                Trip.route_id == route_id,
                Trip.status == TripStatus.SCHEDULED,
                Trip.seats_available > 0,
                Trip.depart_at > now + timedelta(minutes=cutoff_minutes),
            )
            .distinct()
            .order_by(func.date(Trip.depart_at))
            .limit(limit)
        )
        return [value.isoformat() for value in rows]

    async def transport_options(self, route_id: int, date: str) -> list[tuple[int, str, int, int, int]]:
        rows = await self.session.execute(
            select(
                TransportType.id,
                TransportType.code,
                func.min(Trip.price),
                func.count(Trip.id),
                func.sum(Trip.seats_available),
            )
            .join(Trip, Trip.transport_type_id == TransportType.id)
            .where(
                Trip.route_id == route_id,
                func.date(Trip.depart_at) == date,
                Trip.status == TripStatus.SCHEDULED,
                Trip.seats_available > 0,
            )
            .group_by(TransportType.id, TransportType.code)
            .order_by(func.min(Trip.price).desc())
        )
        return [(row[0], row[1].value, int(row[2]), int(row[3]), int(row[4])) for row in rows]

    async def trips_for_choice(self, route_id: int, date: str, transport_type_id: int) -> list[Trip]:
        return list(
            await self.session.scalars(
                select(Trip)
                .where(
                    Trip.route_id == route_id,
                    Trip.transport_type_id == transport_type_id,
                    func.date(Trip.depart_at) == date,
                    Trip.status == TripStatus.SCHEDULED,
                    Trip.seats_available > 0,
                )
                .order_by(Trip.depart_at)
                .limit(6)
            )
        )

    async def destination_regions(
        self, from_region_id: int, language: str, *, cutoff_minutes: int, horizon_days: int
    ) -> list[tuple[int, str]]:
        now = datetime.now(UTC)
        destination = aliased(Region)
        name = destination.name_ru if language == "ru" else destination.name_uz
        rows = await self.session.execute(
            select(distinct(destination.id), name)
            .join(Route, Route.to_region_id == destination.id)
            .join(Trip, Trip.route_id == Route.id)
            .where(
                Route.from_region_id == from_region_id,
                destination.is_active.is_(True),
                Route.is_active.is_(True),
                Trip.status == TripStatus.SCHEDULED,
                Trip.seats_available > 0,
                Trip.depart_at > now + timedelta(minutes=cutoff_minutes),
                Trip.depart_at <= now + timedelta(days=horizon_days),
            )
            .order_by(name)
        )
        return [(row[0], row[1]) for row in rows]
