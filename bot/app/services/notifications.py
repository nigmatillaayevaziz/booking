from collections.abc import Mapping

from app.locales import t


def render_notification(notification_type: str, payload: Mapping[str, object], language: str) -> str:
    number = str(payload.get("number", ""))
    key = {
        "payment_reminder": "notification_payment_reminder",
        "hold_expired": "notification_hold_expired",
        "booking_confirmed": "notification_booking_confirmed",
        "booking_cancelled": "notification_booking_cancelled",
    }.get(notification_type, "notification_updated")
    return t(language, key, number=number)
