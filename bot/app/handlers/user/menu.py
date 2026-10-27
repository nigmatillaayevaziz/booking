from datetime import UTC, datetime, timedelta
from html import escape
from typing import cast

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.security import PIICipher
from app.keyboards.common import main_menu, phone_keyboard
from app.locales import t
from app.models.entities import DataDeletionRequest, Region, Route, RouteFare, User
from app.models.enums import Language
from app.repositories.users import UserRepository
from app.services.phone import normalize_uz_phone
from app.services.pricing import format_uzs
from app.states.settings import SettingsState

router = Router(name="passenger_menu")
settings = get_settings()


def _cipher() -> PIICipher:
    return PIICipher(
        settings.pii_encryption_key.get_secret_value(), settings.phone_hash_key.get_secret_value()
    )


async def _user(telegram_id: int) -> User | None:
    async with session_factory() as session:
        return await UserRepository(session, _cipher()).by_telegram_id(telegram_id)


def _settings_keyboard(language: str, notifications_enabled: bool):  # type: ignore[no-untyped-def]
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="settings:lang:uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="settings:lang:ru"),
    )
    builder.button(text=t(language, "change_phone"), callback_data="settings:phone")
    builder.button(
        text=t(
            language,
            "notifications_on" if notifications_enabled else "notifications_off",
        ),
        callback_data="settings:notifications",
    )
    builder.button(text=t(language, "delete_data"), callback_data="settings:delete")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


@router.message(F.text.in_({"ℹ️ Yordam / Aloqa", "ℹ️ Помощь / Контакты"}))
async def help_menu(message: Message) -> None:
    if not message.from_user:
        return
    user = await _user(message.from_user.id)
    language = user.language.value if user else settings.default_language
    await message.answer(t(language, "help_text", contact=escape(settings.support_contact)))


@router.message(F.text.in_({"⚙️ Sozlamalar", "⚙️ Настройки"}))
async def settings_menu(message: Message) -> None:
    if not message.from_user:
        return
    user = await _user(message.from_user.id)
    if user is None:
        await message.answer(t("uz", "register_first"))
        return
    language = user.language.value
    await message.answer(
        t(language, "settings_title"),
        reply_markup=_settings_keyboard(language, user.notifications_enabled),
    )


@router.callback_query(F.data.startswith("settings:lang:"))
async def change_language(callback: CallbackQuery) -> None:
    if not callback.from_user or callback.data is None:
        return
    language = callback.data.rsplit(":", 1)[-1]
    if language not in {"uz", "ru"}:
        return
    async with session_factory() as session, session.begin():
        repository = UserRepository(session, _cipher())
        user = await repository.by_telegram_id(callback.from_user.id)
        if user is None:
            return
        user.language = Language(language)
        roles = await repository.roles(user.id)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            t(language, "language_changed"),
            reply_markup=main_menu(language, roles),
        )
    await callback.answer()


@router.callback_query(F.data == "settings:phone")
async def begin_phone_change(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user:
        return
    user = await _user(callback.from_user.id)
    if user is None:
        return
    language = user.language.value
    await state.set_state(SettingsState.phone)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            t(language, "share_new_phone"),
            reply_markup=phone_keyboard(language),
        )
    await callback.answer()


@router.message(SettingsState.phone, F.contact)
async def save_new_phone(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.contact:
        return
    user = await _user(message.from_user.id)
    language = user.language.value if user else settings.default_language
    if message.contact.user_id != message.from_user.id:
        await message.answer(t(language, "wrong_contact"))
        return
    try:
        phone = normalize_uz_phone(message.contact.phone_number)
    except ValueError:
        await message.answer(t(language, "wrong_phone_format"))
        return
    pii = _cipher()
    phone_hash = pii.blind_index(phone)
    async with session_factory() as session, session.begin():
        repository = UserRepository(session, pii)
        current = await repository.by_telegram_id(message.from_user.id)
        duplicate = await session.scalar(
            select(User.id).where(User.phone_hash == phone_hash, User.tg_id != message.from_user.id)
        )
        if current is None or duplicate is not None:
            await message.answer(t(language, "phone_already_used"))
            return
        current.phone_encrypted = pii.encrypt(phone)
        current.phone_hash = phone_hash
        roles = await repository.roles(current.id)
    await state.clear()
    await message.answer(
        t(language, "phone_changed"),
        reply_markup=main_menu(language, roles),
    )


@router.callback_query(F.data == "settings:notifications")
async def toggle_notifications(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return
    async with session_factory() as session, session.begin():
        user = await UserRepository(session, _cipher()).by_telegram_id(callback.from_user.id)
        if user is None:
            return
        user.notifications_enabled = not user.notifications_enabled
        language = user.language.value
        enabled = user.notifications_enabled
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t(language, "settings_title"),
            reply_markup=_settings_keyboard(language, enabled),
        )
    await callback.answer(t(language, "notifications_saved"))


@router.callback_query(F.data == "settings:delete")
async def deletion_preview(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return
    user = await _user(callback.from_user.id)
    if user is None:
        return
    language = user.language.value
    builder = InlineKeyboardBuilder()
    builder.button(text=t(language, "confirm_delete_data"), callback_data="settings:delete-confirm")
    builder.button(text=t(language, "back"), callback_data="settings:open")
    builder.adjust(1)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t(language, "delete_data_warning"),
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data == "settings:open")
async def settings_callback(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return
    user = await _user(callback.from_user.id)
    if user is None:
        return
    language = user.language.value
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t(language, "settings_title"),
            reply_markup=_settings_keyboard(language, user.notifications_enabled),
        )
    await callback.answer()


@router.callback_query(F.data == "settings:delete-confirm")
async def create_deletion_request(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return
    async with session_factory() as session, session.begin():
        user = await UserRepository(session, _cipher()).by_telegram_id(callback.from_user.id)
        if user is None:
            return
        language = user.language.value
        existing = await session.scalar(
            select(DataDeletionRequest.id).where(
                DataDeletionRequest.user_id == user.id,
                DataDeletionRequest.status == "requested",
            )
        )
        if existing is None:
            session.add(
                DataDeletionRequest(
                    user_id=user.id,
                    status="requested",
                    due_at=datetime.now(UTC) + timedelta(days=30),
                )
            )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t(language, "delete_data_requested"))
    await callback.answer()


@router.message(F.text.in_({"💳 Narxlar", "💳 Цены"}))
async def prices(message: Message) -> None:
    if not message.from_user:
        return
    user = await _user(message.from_user.id)
    language = user.language.value if user else settings.default_language
    origin = Region.__table__.alias("origin")
    destination = Region.__table__.alias("destination")
    origin_name = origin.c.name_ru if language == "ru" else origin.c.name_uz
    destination_name = destination.c.name_ru if language == "ru" else destination.c.name_uz
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    origin_name,
                    destination_name,
                    RouteFare.taxi_price,
                    RouteFare.bus_price,
                    RouteFare.train_price,
                )
                .join(Route, Route.id == RouteFare.route_id)
                .join(origin, origin.c.id == Route.from_region_id)
                .join(destination, destination.c.id == Route.to_region_id)
                .where(Route.is_active.is_(True))
                .order_by(origin_name, destination_name)
                .limit(30)
            )
        ).all()
    lines: list[str] = []
    for from_name, to_name, taxi, bus, train in rows:
        fares = [
            f"🚕 {format_uzs(cast(int, taxi))}" if taxi is not None else None,
            f"🚌 {format_uzs(cast(int, bus))}" if bus is not None else None,
            f"🚆 {format_uzs(cast(int, train))}" if train is not None else None,
        ]
        lines.append(
            f"<b>{escape(str(from_name))} → {escape(str(to_name))}</b>\n"
            + " · ".join(value for value in fares if value)
        )
    await message.answer(
        f"<b>{t(language, 'prices_title')}</b>\n\n"
        + ("\n\n".join(lines) if lines else t(language, "prices_empty"))
    )
