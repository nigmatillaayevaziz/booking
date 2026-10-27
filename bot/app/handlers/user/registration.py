from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.security import PIICipher
from app.keyboards.common import consent_keyboard, language_keyboard, main_menu, phone_keyboard
from app.locales import t
from app.models.entities import UserConsent
from app.models.enums import Language, RoleCode
from app.repositories.users import UserRepository
from app.services.phone import normalize_uz_phone
from app.states.registration import RegistrationState

router = Router(name="registration")
settings = get_settings()


def cipher() -> PIICipher:
    return PIICipher(
        settings.pii_encryption_key.get_secret_value(), settings.phone_hash_key.get_secret_value()
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return
    async with session_factory() as session, session.begin():
        repository = UserRepository(session, cipher())
        user = await repository.by_telegram_id(message.from_user.id)
        if user and user.consent_at and user.phone_encrypted:
            roles = await repository.roles(user.id)
            current_state = await state.get_state()
            if current_state and current_state.startswith("BookingState:"):
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=t(user.language.value, "resume"),
                                callback_data="reg:resume",
                            ),
                            InlineKeyboardButton(
                                text=t(user.language.value, "restart"),
                                callback_data="reg:restart",
                            ),
                        ]
                    ]
                )
                await message.answer(
                    t(user.language.value, "unfinished_booking"),
                    reply_markup=keyboard,
                )
                return
            await message.answer(
                t(user.language.value, "welcome"),
                reply_markup=main_menu(user.language.value, roles),
            )
            return
    await state.clear()
    await state.set_state(RegistrationState.language)
    await message.answer(t("uz", "choose_language"), reply_markup=language_keyboard())


@router.callback_query(F.data == "reg:resume")
async def resume_booking(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return
    async with session_factory() as session:
        user = await UserRepository(session, cipher()).by_telegram_id(callback.from_user.id)
    language = user.language.value if user else settings.default_language
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t(language, "resume_hint"))
    await callback.answer()


@router.callback_query(F.data == "reg:restart")
async def restart_booking(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user:
        return
    await state.clear()
    async with session_factory() as session:
        repository = UserRepository(session, cipher())
        user = await repository.by_telegram_id(callback.from_user.id)
        if user is None:
            return
        roles = await repository.roles(user.id)
        language = user.language.value
    if isinstance(callback.message, Message):
        await callback.message.answer(
            t(language, "restarted"),
            reply_markup=main_menu(language, roles),
        )
    await callback.answer()


@router.callback_query(RegistrationState.language, F.data.startswith("reg:lang:"))
async def choose_language(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not callback.message:
        return
    language = callback.data.rsplit(":", 1)[-1] if callback.data else "uz"
    if language not in {"uz", "ru"}:
        await callback.answer("Invalid language", show_alert=True)
        return
    async with session_factory() as session, session.begin():
        repository = UserRepository(session, cipher())
        full_name = " ".join(filter(None, [callback.from_user.first_name, callback.from_user.last_name]))
        user = await repository.ensure_user(callback.from_user.id, full_name, language)
        user.language = Language(language)
        if callback.from_user.id in settings.admin_ids:
            await repository.grant_role(user.id, RoleCode.SUPER_ADMIN)
    await state.update_data(language=language)
    await state.set_state(RegistrationState.phone)
    await callback.message.answer(t(language, "welcome"))
    await callback.message.answer(t(language, "share_phone"), reply_markup=phone_keyboard(language))
    await callback.answer()


@router.message(RegistrationState.phone, F.contact)
async def receive_phone(message: Message, state: FSMContext) -> None:
    if not message.from_user or not message.contact:
        return
    data = await state.get_data()
    language = data.get("language", "uz")
    if message.contact.user_id != message.from_user.id:
        await message.answer(t(language, "wrong_contact"))
        return
    try:
        phone = normalize_uz_phone(message.contact.phone_number)
    except ValueError:
        await message.answer(t(language, "wrong_phone_format"))
        return
    pii = cipher()
    async with session_factory() as session, session.begin():
        user = await UserRepository(session, pii).by_telegram_id(message.from_user.id)
        if user is None:
            return
        user.phone_encrypted = pii.encrypt(phone)
        user.phone_hash = pii.blind_index(phone)
    await state.set_state(RegistrationState.consent)
    await message.answer(t(language, "terms"), reply_markup=ReplyKeyboardRemove())
    await message.answer(t(language, "terms"), reply_markup=consent_keyboard(language))


@router.callback_query(RegistrationState.consent, F.data == "reg:consent:accept")
async def accept_consent(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not callback.message:
        return
    async with session_factory() as session, session.begin():
        repository = UserRepository(session, cipher())
        user = await repository.by_telegram_id(callback.from_user.id)
        if user is None:
            return
        user.consent_at = datetime.now(UTC)
        user.terms_version = "1.0"
        user.privacy_version = "1.0"
        session.add(
            UserConsent(
                user_id=user.id,
                terms_version="1.0",
                privacy_version="1.0",
                accepted_at=user.consent_at,
            )
        )
        roles = await repository.roles(user.id)
        language = user.language.value
    await state.clear()
    await callback.message.answer(t(language, "registered"), reply_markup=main_menu(language, roles))
    await callback.answer()
