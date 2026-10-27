from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.locales import t


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="reg:lang:uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="reg:lang:ru"),
    ]])


def phone_keyboard(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(language, "share_phone_button"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def consent_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(language, "accept"), callback_data="reg:consent:accept")
    ]])


def main_menu(language: str, role_codes: set[str] | None = None) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(language, "book"))],
        [KeyboardButton(text=t(language, "my_bookings")), KeyboardButton(text=t(language, "prices"))],
        [KeyboardButton(text=t(language, "help")), KeyboardButton(text=t(language, "settings"))],
    ]
    roles = role_codes or set()
    if roles & {"driver", "operator", "admin", "super_admin"}:
        rows.append([KeyboardButton(text="🧰 Boshqaruv / Управление")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def regions_keyboard(items: list[tuple[int, str]], prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for region_id, name in items:
        builder.button(text=name, callback_data=f"book:{prefix}:{region_id}")
    builder.adjust(2)
    return builder.as_markup()
