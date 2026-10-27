from decimal import Decimal

import pytest

from app.services.pricing import PricingError, RoutePrices, booking_total, commission_amount, format_uzs


def test_valid_price_hierarchy() -> None:
    RoutePrices(taxi=180_000, bus=110_000, train=85_000).validate()


@pytest.mark.parametrize(
    "prices",
    [
        RoutePrices(taxi=100_000, bus=100_000, train=80_000),
        RoutePrices(taxi=180_000, bus=80_000, train=90_000),
        RoutePrices(taxi=70_000, bus=None, train=85_000),
    ],
)
def test_invalid_price_hierarchy(prices: RoutePrices) -> None:
    with pytest.raises(PricingError):
        prices.validate()


def test_total_commission_and_format() -> None:
    assert booking_total(180_000, 2) == 360_000
    assert commission_amount(360_000, Decimal("7.5")) == 27_000
    assert format_uzs(180_000) == "180 000 so‘m"
