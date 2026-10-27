from sqlalchemy import Enum

from app.models.entities import Booking, Role, TransportType, Trip, User


def test_database_enums_use_public_lowercase_values() -> None:
    columns = [
        User.__table__.c.language,
        Role.__table__.c.code,
        TransportType.__table__.c.code,
        Trip.__table__.c.status,
        Booking.__table__.c.status,
    ]

    for column in columns:
        assert isinstance(column.type, Enum)
        assert all(value == value.lower() for value in column.type.enums)

    assert "pending_payment" in Booking.__table__.c.status.type.enums
    assert "PENDING_PAYMENT" not in Booking.__table__.c.status.type.enums
