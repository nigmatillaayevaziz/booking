from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


class PricingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RoutePrices:
    taxi: int | None
    bus: int | None
    train: int | None

    def validate(self) -> None:
        values = {"taxi": self.taxi, "bus": self.bus, "train": self.train}
        for name, value in values.items():
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
                raise PricingError(f"{name} narxi musbat butun son bo‘lishi kerak")
        if self.taxi is not None and self.bus is not None and self.taxi <= self.bus:
            raise PricingError("Taxi narxi avtobus narxidan yuqori bo‘lishi kerak")
        if self.bus is not None and self.train is not None and self.bus <= self.train:
            raise PricingError("Avtobus narxi poyezd narxidan yuqori bo‘lishi kerak")
        if self.taxi is not None and self.train is not None and self.taxi <= self.train:
            raise PricingError("Taxi narxi poyezd narxidan yuqori bo‘lishi kerak")
        if all(value is None for value in values.values()):
            raise PricingError("Kamida bitta transport narxi kiritilishi kerak")


def booking_total(unit_price: int, passengers: int, discount: int = 0) -> int:
    if unit_price <= 0:
        raise PricingError("Reys narxi musbat bo‘lishi kerak")
    if not 1 <= passengers <= 5:
        raise PricingError("Yo‘lovchilar soni 1–5 oralig‘ida bo‘lishi kerak")
    subtotal = unit_price * passengers
    if discount < 0 or discount > subtotal:
        raise PricingError("Chegirma summasi noto‘g‘ri")
    return subtotal - discount


def commission_amount(total: int, percent: Decimal) -> int:
    if total < 0 or percent < 0 or percent > 100:
        raise PricingError("Komissiya qiymati noto‘g‘ri")
    return int((Decimal(total) * percent / Decimal(100)).quantize(Decimal("1"), ROUND_HALF_UP))


def format_uzs(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " so‘m"
