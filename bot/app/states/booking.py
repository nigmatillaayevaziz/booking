from aiogram.fsm.state import State, StatesGroup


class BookingState(StatesGroup):
    from_region = State()
    to_region = State()
    date = State()
    transport_type = State()
    trip = State()
    passengers = State()
    pickup = State()
    passenger_names = State()
    confirm = State()
    payment = State()
