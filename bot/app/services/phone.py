import re

UZ_PHONE_PATTERN = re.compile(r"^\+998\d{9}$")


def normalize_uz_phone(value: str) -> str:
    normalized = re.sub(r"[\s()\-]", "", value)
    if normalized.startswith("998"):
        normalized = f"+{normalized}"
    elif len(normalized) == 9 and normalized.isdigit():
        normalized = f"+998{normalized}"
    if not UZ_PHONE_PATTERN.fullmatch(normalized):
        raise ValueError("Telefon raqami +998XXXXXXXXX formatida bo‘lishi kerak")
    return normalized
