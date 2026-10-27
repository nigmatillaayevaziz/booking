from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    language = State()
    phone = State()
    consent = State()
