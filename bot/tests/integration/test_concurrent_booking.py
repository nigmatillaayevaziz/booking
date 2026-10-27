import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import PIICipher
from app.models import Base
from app.models.entities import Region, Route, TransportType, Trip, User
from app.models.enums import Language, TransportCode, TripStatus
from app.services.booking import BookingError, create_hold

pytestmark = pytest.mark.integration
TEST_DSN = os.getenv("TEST_POSTGRES_DSN")


@pytest.mark.skipif(not TEST_DSN, reason="TEST_POSTGRES_DSN is required")
async def test_only_one_of_fifty_requests_gets_the_last_seat() -> None:
    engine = create_async_engine(TEST_DSN, pool_size=60)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with factory() as session, session.begin():
        session.add_all([
            User(id=1, tg_id=1, full_name_encrypted="test", language=Language.UZ),
            Region(id=1, name_uz="Toshkent", name_ru="Ташкент", sort_order=1),
            Region(id=2, name_uz="Samarqand", name_ru="Самарканд", sort_order=2),
            TransportType(
                id=1,
                code=TransportCode.TAXI,
                name_uz="Taxi",
                name_ru="Такси",
                commission_pct=Decimal("10"),
                max_passengers_per_booking=4,
            ),
            Route(id=1, from_region_id=1, to_region_id=2, duration_min=240),
            Trip(
                id=1,
                route_id=1,
                transport_type_id=1,
                depart_at=datetime.now(UTC) + timedelta(days=1),
                arrive_at_est=datetime.now(UTC) + timedelta(days=1, hours=4),
                seats_total=1,
                seats_available=1,
                price=180_000,
                status=TripStatus.SCHEDULED,
            ),
        ])

    settings = SimpleNamespace(
        max_active_holds=3,
        booking_cutoff_minutes=60,
        booking_horizon_days=30,
        hold_minutes=15,
    )
    cipher = PIICipher(Fernet.generate_key().decode(), "hash-key-for-tests")

    async def attempt(index: int) -> bool:
        try:
            async with factory() as session, session.begin():
                await create_hold(
                    session,
                    settings=settings,
                    cipher=cipher,
                    user_id=1,
                    trip_id=1,
                    passenger_names=[f"Passenger {index}"],
                )
            return True
        except BookingError:
            return False

    results = await asyncio.gather(*(attempt(index) for index in range(50)))
    assert sum(results) == 1
    await engine.dispose()
