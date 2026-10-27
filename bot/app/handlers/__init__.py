from aiogram import Dispatcher

from app.handlers.admin.payments import router as admin_payments_router
from app.handlers.user.booking import router as booking_router
from app.handlers.user.menu import router as passenger_menu_router
from app.handlers.user.my_bookings import router as my_bookings_router
from app.handlers.user.registration import router as registration_router


def register_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(registration_router)
    dispatcher.include_router(booking_router)
    dispatcher.include_router(my_bookings_router)
    dispatcher.include_router(passenger_menu_router)
    dispatcher.include_router(admin_payments_router)
