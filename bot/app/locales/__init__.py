import json
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).parent


@lru_cache(maxsize=2)
def load_locale(language: str) -> dict[str, str]:
    code = language if language in {"uz", "ru"} else "uz"
    payload: object = json.loads((LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
    ):
        raise ValueError(f"{code}.json faqat matn kalitlari va qiymatlaridan iborat bo‘lishi kerak")
    return {str(key): str(value) for key, value in payload.items()}


def t(language: str, key: str, **values: object) -> str:
    messages = load_locale(language)
    template = messages.get(key) or load_locale("uz").get(key) or key
    return template.format(**values)
