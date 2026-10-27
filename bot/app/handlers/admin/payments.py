from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.core.config import get_settings
from app.core.context import get_request_id
from app.core.db import session_factory
from app.core.security import PIICipher
from app.repositories.users import UserRepository
from app.services.booking import BookingError, confirm_manual_payment
from app.services.pricing import format_uzs

router = Router(name="admin_payments")
settings = get_settings()


def _cipher() -> PIICipher:
    return PIICipher(
        settings.pii_encryption_key.get_secret_value(), settings.phone_hash_key.get_secret_value()
    )


@router.message(Command("confirm_payment"))
async def confirm_payment(message: Message, command: CommandObject) -> None:
    if not message.from_user:
        return
    async with session_factory() as session:
        repository = UserRepository(session, _cipher())
        actor = await repository.by_telegram_id(message.from_user.id)
        roles = await repository.roles(actor.id) if actor else set()
    if message.from_user.id not in settings.admin_ids and not roles & {"operator", "admin", "super_admin"}:
        await message.answer("⛔ Ruxsat yo‘q.")
        return
    if actor is None:
        await message.answer("Avval /start orqali ro‘yxatdan o‘ting.")
        return
    try:
        booking_id = int(command.args or "")
    except ValueError:
        await message.answer("Format: <code>/confirm_payment BOOKING_ID</code>")
        return
    try:
        async with session_factory() as session, session.begin():
            booking = await confirm_manual_payment(
                session,
                booking_id=booking_id,
                actor_user_id=actor.id,
                external_id=f"telegram:{message.from_user.id}:{message.message_id}",
                request_id=get_request_id(),
            )
    except BookingError as error:
        await message.answer(f"❌ {error}")
        return
    await message.answer(
        f"✅ Buyurtma #{booking.number} tasdiqlandi. Jami: {format_uzs(booking.total_price)}"
    )
