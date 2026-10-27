import pytest

from app.services.phone import normalize_uz_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+998901234567", "+998901234567"),
        ("998 90 123 45 67", "+998901234567"),
        ("90-123-45-67", "+998901234567"),
        ("(90) 123-45-67", "+998901234567"),
    ],
)
def test_normalize_uz_phone(raw: str, expected: str) -> None:
    assert normalize_uz_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "+79991234567", "+998123", "abc"])
def test_reject_invalid_uz_phone(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_uz_phone(raw)
