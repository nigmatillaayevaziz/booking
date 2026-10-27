from app.services.notifications import render_notification


def test_notification_is_rendered_in_user_language() -> None:
    assert "tasdiqlandi" in render_notification("booking_confirmed", {"number": "TB-123"}, "uz")
    assert "подтверждён" in render_notification(
        "booking_confirmed", {"number": "TB-123"}, "ru"
    )
