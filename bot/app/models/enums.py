from enum import StrEnum


class Language(StrEnum):
    UZ = "uz"
    RU = "ru"


class RoleCode(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"
    OPERATOR = "operator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class TransportCode(StrEnum):
    TAXI = "taxi"
    BUS = "bus"
    TRAIN = "train"


class TripStatus(StrEnum):
    SCHEDULED = "scheduled"
    BOARDING = "boarding"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class BookingStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    NO_SHOW = "no_show"


class PaymentStatus(StrEnum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
