from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.security import PIICipher
from app.keyboards.common import regions_keyboard
from app.locales import t
from app.models.entities import Trip
from app.repositories.trips import TripRepository
from app.repositories.users import UserRepository
from app.services.booking import BookingError, cancel_booking, create_hold
from app.services.pricing import format_uzs
from app.states.booking import BookingState

router = Router(name="booking")
settings = get_settings()


def _cipher() -> PIICipher:
    return PIICipher(
        settings.pii_encryption_key.get_secret_value(), settings.phone_hash_key.get_secret_value()
    )


async def _language(telegram_id: int) -> str:
    async with session_factory() as session:
        user = await UserRepository(session, _cipher()).by_telegram_id(telegram_id)
        return user.language.value if user else settings.default_language


@router.message(F.text.in_({"🎫 Buyurtma berish", "🎫 Забронировать"}))
async def begin_booking(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return
    language = await _language(message.from_user.id)
    async with session_factory() as session:
        items = await TripRepository(session).origin_regions(
            language,
            cutoff_minutes=settings.booking_cutoff_minutes,
            horizon_days=settings.booking_horizon_days,
        )
    if not items:
        await message.answer(t(language, "no_routes"))
        return
    await state.set_state(BookingState.from_region)
    await state.update_data(language=language)
    await message.answer(t(language, "choose_from"), reply_markup=regions_keyboard(items, "from"))


@router.callback_query(BookingState.from_region, F.data.startswith("book:from:"))
async def choose_origin(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    region_id = int(callback.data.rsplit(":", 1)[-1])
    data = await state.get_data()
    language = data.get("language", "uz")
    async with session_factory() as session:
        items = await TripRepository(session).destination_regions(
            region_id,
            language,
            cutoff_minutes=settings.booking_cutoff_minutes,
            horizon_days=settings.booking_horizon_days,
        )
    if not items:
        await callback.answer(t(language, "no_routes"), show_alert=True)
        return
    await state.update_data(from_region_id=region_id)
    await state.set_state(BookingState.to_region)
    prompt = "📍 Qayerga borasiz?" if language == "uz" else "📍 Куда вы едете?"
    await callback.message.edit_text(prompt, reply_markup=regions_keyboard(items, "to"))
    await callback.answer()


@router.callback_query(BookingState.to_region, F.data.startswith("book:to:"))
async def choose_destination(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    to_region_id = int(callback.data.rsplit(":", 1)[-1])
    data = await state.get_data()
    async with session_factory() as session:
        repository = TripRepository(session)
        route_id = await repository.route_id(data["from_region_id"], to_region_id)
        dates = (
            await repository.available_dates(route_id, settings.booking_cutoff_minutes) if route_id else []
        )
    if not route_id or not dates:
        await callback.answer(t(data.get("language", "uz"), "no_routes"), show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for value in dates:
        builder.button(text=".".join(reversed(value.split("-"))), callback_data=f"book:date:{value}")
    builder.adjust(2)
    await state.update_data(to_region_id=to_region_id, route_id=route_id)
    await state.set_state(BookingState.date)
    await callback.message.edit_text("📅 Sanani tanlang / Выберите дату", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(BookingState.date, F.data.startswith("book:date:"))
async def choose_date(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    value = callback.data.removeprefix("book:date:")
    data = await state.get_data()
    async with session_factory() as session:
        options = await TripRepository(session).transport_options(data["route_id"], value)
    if not options:
        await callback.answer(t(data.get("language", "uz"), "no_routes"), show_alert=True)
        return
    icons = {"taxi": "🚕", "bus": "🚌", "train": "🚆"}
    builder = InlineKeyboardBuilder()
    for type_id, code, price, trips, seats in options:
        builder.button(
            text=f"{icons[code]} {format_uzs(price)} · {trips} reys · {seats} joy",
            callback_data=f"book:type:{type_id}:{code}",
        )
    builder.adjust(1)
    await state.update_data(date=value)
    await state.set_state(BookingState.transport_type)
    await callback.message.edit_text(
        "🚐 Transport turini tanlang / Выберите транспорт",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(BookingState.transport_type, F.data.startswith("book:type:"))
async def choose_transport(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    _, _, type_value, code = callback.data.split(":")
    type_id = int(type_value)
    data = await state.get_data()
    async with session_factory() as session:
        trips = await TripRepository(session).trips_for_choice(data["route_id"], data["date"], type_id)
    builder = InlineKeyboardBuilder()
    for trip in trips:
        local_time = trip.depart_at.astimezone(ZoneInfo(settings.timezone))
        builder.button(
            text=f"🕐 {local_time:%H:%M} · {trip.seats_available} joy · {format_uzs(trip.price)}",
            callback_data=f"book:trip:{trip.id}",
        )
    builder.adjust(1)
    await state.update_data(transport_type_id=type_id, transport_code=code)
    await state.set_state(BookingState.trip)
    await callback.message.edit_text("🕐 Reysni tanlang / Выберите рейс", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(BookingState.trip, F.data.startswith("book:trip:"))
async def choose_trip(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    trip_id = int(callback.data.rsplit(":", 1)[-1])
    async with session_factory() as session:
        trip = await session.get(Trip, trip_id)
    if not trip or trip.seats_available < 1:
        await callback.answer("Joy qolmadi / Мест нет", show_alert=True)
        return
    data = await state.get_data()
    maximum = min(trip.seats_available, 4 if data["transport_code"] == "taxi" else 5)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=str(value), callback_data=f"book:passengers:{value}")
                for value in range(1, maximum + 1)
            ]
        ]
    )
    await state.update_data(trip_id=trip_id, unit_price=trip.price, depart_at=trip.depart_at.isoformat())
    await state.set_state(BookingState.passengers)
    await callback.message.edit_text("👥 Yo‘lovchilar soni / Количество пассажиров", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BookingState.passengers, F.data.startswith("book:passengers:"))
async def choose_passengers(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message) or callback.data is None:
        return
    count = int(callback.data.rsplit(":", 1)[-1])
    data = await state.get_data()
    await state.update_data(passengers=count)
    if data["transport_code"] == "taxi":
        await state.set_state(BookingState.pickup)
        await callback.message.edit_text("📍 Olib ketish manzilini yozing / Укажите адрес подачи")
    else:
        await state.update_data(pickup_address=None)
        await state.set_state(BookingState.passenger_names)
        await callback.message.edit_text(f"👤 {count} ta yo‘lovchi ismini vergul bilan kiriting")
    await callback.answer()


@router.message(BookingState.pickup, F.text)
async def receive_pickup(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    value = message.text.strip()
    if len(value) < 5 or len(value) > 300:
        await message.answer("Manzil 5–300 belgidan iborat bo‘lsin.")
        return
    data = await state.get_data()
    await state.update_data(pickup_address=value)
    await state.set_state(BookingState.passenger_names)
    await message.answer(f"👤 {data['passengers']} ta yo‘lovchi ismini vergul bilan kiriting")


@router.message(BookingState.passenger_names, F.text)
async def receive_names(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return
    names = [item.strip() for item in message.text.split(",") if item.strip()]
    data = await state.get_data()
    if len(names) != data["passengers"] or any(len(name) < 2 or len(name) > 100 for name in names):
        await message.answer(f"Aynan {data['passengers']} ta to‘liq ismni vergul bilan kiriting.")
        return
    total = data["unit_price"] * data["passengers"]
    await state.update_data(passenger_names=names)
    await state.set_state(BookingState.confirm)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ To‘lash", callback_data="book:confirm")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="book:cancel")],
        ]
    )
    await message.answer(
        "✅ <b>Buyurtmani tekshiring</b>\n\n"
        f"👥 {', '.join(names)}\n"
        f"💳 {format_uzs(data['unit_price'])} × {data['passengers']} = <b>{format_uzs(total)}</b>\n\n"
        f"⏳ To‘lov uchun {settings.hold_minutes} daqiqa beriladi.",
        reply_markup=keyboard,
    )


@router.callback_query(BookingState.confirm, F.data == "book:confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not isinstance(callback.message, Message):
        return
    data = await state.get_data()
    try:
        async with session_factory() as session, session.begin():
            user = await UserRepository(session, _cipher()).by_telegram_id(callback.from_user.id)
            if user is None:
                raise BookingError("Avval ro‘yxatdan o‘ting")
            booking = await create_hold(
                session,
                settings=settings,
                cipher=_cipher(),
                user_id=user.id,
                trip_id=data["trip_id"],
                passenger_names=data["passenger_names"],
                pickup_address=data.get("pickup_address"),
            )
    except BookingError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await state.set_state(BookingState.payment)
    await state.update_data(booking_id=booking.id)
    await callback.message.edit_text(
        f"⏳ <b>Buyurtma #{booking.number}</b> yaratildi.\n"
        f"Jami: <b>{format_uzs(booking.total_price)}</b>\n\n"
        "Operator to‘lovni tasdiqlaguncha joylaringiz 15 daqiqa ushlab turiladi."
    )
    await callback.answer("Joylar vaqtincha band qilindi")


@router.callback_query(F.data == "book:cancel")
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    booking_id = data.get("booking_id")
    if booking_id and callback.from_user:
        try:
            async with session_factory() as session, session.begin():
                user = await UserRepository(session, _cipher()).by_telegram_id(callback.from_user.id)
                if user:
                    await cancel_booking(session, booking_id=booking_id, requested_by_user_id=user.id)
        except BookingError:
            pass
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("❌ Jarayon bekor qilindi.")
    await callback.answer()
