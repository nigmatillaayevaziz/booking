from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CancellationPolicy:
    over_24h: int = 100
    from_6h_to_24h: int = 70
    from_1h_to_6h: int = 30
    under_1h: int = 0

    def __post_init__(self) -> None:
        for value in (self.over_24h, self.from_6h_to_24h, self.from_1h_to_6h, self.under_1h):
            if not 0 <= value <= 100:
                raise ValueError("Qaytarish foizi 0–100 oralig‘ida bo‘lishi kerak")


DEFAULT_CANCELLATION_POLICY = CancellationPolicy()


@dataclass(frozen=True, slots=True)
class RefundQuote:
    percent: int
    amount: int


def refund_quote(
    total_price: int,
    depart_at: datetime,
    now: datetime,
    policy: CancellationPolicy | None = None,
    company_cancelled: bool = False,
) -> RefundQuote:
    policy = policy or DEFAULT_CANCELLATION_POLICY
    if depart_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("Vaqtlar timezone-aware bo‘lishi kerak")
    if total_price < 0:
        raise ValueError("Summa manfiy bo‘lishi mumkin emas")
    seconds = (depart_at - now).total_seconds()
    if company_cancelled:
        percent = 100
    elif seconds > 24 * 3600:
        percent = policy.over_24h
    elif seconds > 6 * 3600:
        percent = policy.from_6h_to_24h
    elif seconds >= 3600:
        percent = policy.from_1h_to_6h
    else:
        percent = policy.under_1h
    return RefundQuote(percent=percent, amount=total_price * percent // 100)


def booking_refund_quote(
    total_price: int,
    depart_at: datetime,
    now: datetime,
    *,
    payment_received: bool,
    policy: CancellationPolicy | None = None,
    company_cancelled: bool = False,
) -> RefundQuote:
    if not payment_received:
        return RefundQuote(percent=0, amount=0)
    return refund_quote(total_price, depart_at, now, policy, company_cancelled)
