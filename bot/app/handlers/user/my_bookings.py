from datetime import UTC, datetime
from html import escape

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.security import PIICipher
from app.locales import t
from app.models.enums import BookingStatus
from app.repositories.bookings import BookingRepository, BookingSummary
from app.repositories.users import UserRepository
from app.services.booking import BookingError, cancel_booking
from app.services.cancellation import booking_refund_quote
from app.services.pricing import format_uzs
from app.services.tickets import ticket_payload, ticket_qr_png

router = Router(name="my_bookings")
settings = get_settings()

ACTIVE_STATUSES = {
    BookingStatus.PENDING_PAYMENT,
    BookingStatus.CONFIRMED,
    BookingStatus.REFUND_PENDING,
}
COMPLETED_STATUSES = {BookingStatus.COMPLETED}
CANCELLED_STATUSES = {
    BookingStatus.EXPIRED,
    BookingStatus.CANCELLED,
    BookingStatus.REFUNDED,
    BookingStatus.NO_SHOW,
}
SECTION_STATUSES = {
    "active": ACTIVE_STATUSES,
    "completed": COMPLETED_STATUSES,
    "cancelled": CANCELLED_STATUSES,
}


def _cipher() -> PIICipher:
    return PIICipher(
        settings.pii_encryption_key.get_secret_value(), settings.phone_hash_key.get_secret_value()
    )


def _status(language: str, status: BookingStatus) -> str:
    return t(language, f"booking_status_{status.value}")


def _summary_text(language: str, item: BookingSummary) -> str:
    local_time = item.depart_at.astimezone(settings.tzinfo)
    return (
        f"<b>#{escape(item.number)}</b> · {_status(language, item.status)}\n"
        f"📍 {escape(item.from_region)} → {escape(item.to_region)}\n"
        f"🗓 {local_time:%d.%m.%Y %H:%M} · {escape(item.transport)}\n"
        f"👥 {item.passengers_count} · 💳 {format_uzs(item.total_price)}"
    )


async def _user_context(telegram_id: int):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        user = await UserRepository(session, _cipher()).by_telegram_id(telegram_id)
        if user is None:
            return None
        return user.id, user.language.value


async def _show_list(message: Message, telegram_id: int, section: str, *, edit: bool = False) -> None:
    context = await _user_context(telegram_id)
    if context is None:
        await message.answer(t("uz", "register_first"))
        return
    user_id, language = context
    statuses = SECTION_STATUSES.get(section, ACTIVE_STATUSES)
    async with session_factory() as session:
        items = await BookingRepository(session).list_for_user(user_id, language, statuses)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t(language, "bookings_active"), callback_data="my:list:active"),
        InlineKeyboardButton(text=t(language, "bookings_completed"), callback_data="my:list:completed"),
        InlineKeyboardButton(text=t(language, "bookings_cancelled"), callback_data="my:list:cancelled"),
    )
    for item in items:
        buttons = [
            InlineKeyboardButton(
                text=f"🔎 #{item.number}", callback_data=f"my:details:{item.id}"
            )
        ]
        if item.status in {BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED}:
            buttons.append(
                InlineKeyboardButton(text=t(language, "cancel"), callback_data=f"my:cancel:{item.id}")
            )
        builder.row(*buttons)

    body = "\n\n".join(_summary_text(language, item) for item in items)
    text = f"<b>{t(language, f'bookings_{section}')}</b>\n\n{body or t(language, 'bookings_empty')}"
    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.message(F.text.in_({"📋 Mening buyurtmalarim", "📋 Мои заказы"}))
async def my_bookings(message: Message) -> None:
    if message.from_user:
        await _show_list(message, message.from_user.id, "active")


@router.callback_query(F.data.startswith("my:list:"))
async def switch_section(callback: CallbackQuery) -> None:
    if not callback.from_user or not isinstance(callback.message, Message) or callback.data is None:
        return
    section = callback.data.rsplit(":", 1)[-1]
    if section not in SECTION_STATUSES:
        await callback.answer()
        return
    await _show_list(callback.message, callback.from_user.id, section, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("my:details:"))
async def booking_details(callback: CallbackQuery) -> None:
    if not callback.from_user or not isinstance(callback.message, Message) or callback.data is None:
        return
    context = await _user_context(callback.from_user.id)
    if context is None:
        return
    user_id, language = context
    booking_id = int(callback.data.rsplit(":", 1)[-1])
    async with session_factory() as session:
        repository = BookingRepository(session)
        item = await repository.summary_for_user(booking_id, user_id, language)
        encrypted_names = await repository.passenger_names(booking_id) if item else []
    if item is None:
        await callback.answer(t(language, "booking_not_found"), show_alert=True)
        return
    names = [escape(_cipher().decrypt(value) or "—") for value in encrypted_names]
    builder = InlineKeyboardBuilder()
    if item.status == BookingStatus.CONFIRMED:
        builder.button(text=t(language, "resend_ticket"), callback_data=f"my:ticket:{item.id}")
    if item.status in {BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED}:
        builder.button(text=t(language, "cancel"), callback_data=f"my:cancel:{item.id}")
    builder.button(text=t(language, "back"), callback_data="my:list:active")
    builder.adjust(1)
    await callback.message.edit_text(
        f"{_summary_text(language, item)}\n\n👤 {', '.join(names)}",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("my:ticket:"))
async def resend_ticket(callback: CallbackQuery) -> None:
    if not callback.from_user or callback.data is None:
        return
    bot = callback.bot
    if bot is None:
        return
    context = await _user_context(callback.from_user.id)
    if context is None:
        return
    user_id, language = context
    booking_id = int(callback.data.rsplit(":", 1)[-1])
    async with session_factory() as session:
        item = await BookingRepository(session).summary_for_user(booking_id, user_id, language)
    if item is None or item.status != BookingStatus.CONFIRMED:
        await callback.answer(t(language, "ticket_unavailable"), show_alert=True)
        return
    payload = ticket_payload(item.number, settings.app_secret.get_secret_value())
    await bot.send_photo(
        callback.from_user.id,
        BufferedInputFile(ticket_qr_png(payload), filename=f"{item.number}.png"),
        caption=f"🎫 <b>#{escape(item.number)}</b>\n{_summary_text(language, item)}",
    )
    await callback.answer(t(language, "ticket_sent"))


@router.callback_query(F.data.startswith("my:cancel:"))
async def cancellation_preview(callback: CallbackQuery) -> None:
    if not callback.from_user or not isinstance(callback.message, Message) or callback.data is None:
        return
    context = await _user_context(callback.from_user.id)
    if context is None:
        return
    user_id, language = context
    booking_id = int(callback.data.rsplit(":", 1)[-1])
    async with session_factory() as session:
        item = await BookingRepository(session).summary_for_user(booking_id, user_id, language)
    if item is None or item.status not in {BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED}:
        await callback.answer(t(language, "cannot_cancel"), show_alert=True)
        return
    quote = booking_refund_quote(
        item.total_price,
        item.depart_at,
        datetime.now(UTC),
        payment_received=item.status == BookingStatus.CONFIRMED,
    )
    builder = InlineKeyboardBuilder()
    builder.button(text=t(language, "confirm_cancel"), callback_data=f"my:cancel-confirm:{item.id}")
    builder.button(text=t(language, "back"), callback_data=f"my:details:{item.id}")
    builder.adjust(1)
    await callback.message.edit_text(
        f"{_summary_text(language, item)}\n\n"
        f"{t(language, 'refund_preview', percent=quote.percent, amount=format_uzs(quote.amount))}",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("my:cancel-confirm:"))
async def cancellation_confirm(callback: CallbackQuery) -> None:
    if not callback.from_user or not isinstance(callback.message, Message) or callback.data is None:
        return
    context = await _user_context(callback.from_user.id)
    if context is None:
        return
    user_id, language = context
    booking_id = int(callback.data.rsplit(":", 1)[-1])
    try:
        async with session_factory() as session, session.begin():
            _, quote = await cancel_booking(
                session,
                booking_id=booking_id,
                requested_by_user_id=user_id,
            )
    except BookingError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.message.edit_text(
        t(language, "booking_cancelled_result", amount=format_uzs(quote.amount))
    )
    await callback.answer()
