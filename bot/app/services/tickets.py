import hashlib
import hmac
from io import BytesIO

import qrcode


def ticket_payload(booking_number: str, secret: str) -> str:
    signature = hmac.new(secret.encode(), booking_number.encode(), hashlib.sha256).hexdigest()[:24]
    return f"uzbooking:{booking_number}:{signature}"


def verify_ticket_payload(payload: str, secret: str) -> bool:
    try:
        prefix, booking_number, signature = payload.split(":", 2)
    except ValueError:
        return False
    expected = ticket_payload(booking_number, secret)
    return prefix == "uzbooking" and hmac.compare_digest(payload, expected) and len(signature) == 24


def ticket_qr_png(payload: str) -> bytes:
    image = qrcode.make(payload)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
