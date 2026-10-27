import asyncio
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.db import engine, session_factory
from app.models.entities import Booking, NotificationOutbox, User
from app.models.enums import BookingStatus, NotificationStatus
from app.services.notifications import render_notification
from app.tasks.celery_app import celery_app

settings = get_settings()


async def _claim(limit: int = 25) -> list[int]:
    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        rows = list(
            await session.scalars(
                select(NotificationOutbox)
                .where(
                    NotificationOutbox.scheduled_at <= now,
                    or_(
                        NotificationOutbox.status == NotificationStatus.PENDING,
                        (
                            (NotificationOutbox.status == NotificationStatus.PROCESSING)
                            & (NotificationOutbox.locked_at < now - timedelta(minutes=5))
                        ),
                    ),
                )
                .order_by(NotificationOutbox.scheduled_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for item in rows:
            item.status = NotificationStatus.PROCESSING
            item.locked_at = now
        return [item.id for item in rows]


async def _deliver() -> int:
    ids = await _claim()
    if not ids:
        return 0
    bot = Bot(
        settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    delivered = 0
    try:
        for item_id in ids:
            async with session_factory() as session:
                item = await session.get(NotificationOutbox, item_id)
                user = await session.get(User, item.user_id) if item else None
                if not item or not user:
                    continue
                try:
                    if item.type == "payment_reminder":
                        booking_id = item.payload.get("booking_id")
                        booking = await session.get(Booking, booking_id) if booking_id else None
                        if booking is None or booking.status != BookingStatus.PENDING_PAYMENT:
                            item.status = NotificationStatus.SENT
                            item.sent_at = datetime.now(UTC)
                            item.last_error = "skipped_stale"
                            await session.commit()
                            continue
                    if not user.notifications_enabled:
                        item.status = NotificationStatus.SENT
                        item.sent_at = datetime.now(UTC)
                        item.last_error = "skipped_notifications_disabled"
                        await session.commit()
                        continue
                    await bot.send_message(
                        user.tg_id,
                        render_notification(item.type, item.payload, user.language.value),
                    )
                    item.status = NotificationStatus.SENT
                    item.sent_at = datetime.now(UTC)
                    delivered += 1
                except TelegramForbiddenError:
                    user.is_blocked_bot = True
                    item.status = NotificationStatus.FAILED
                    item.last_error = "bot_blocked"
                except TelegramRetryAfter as error:
                    item.status = NotificationStatus.PENDING
                    item.attempts += 1
                    item.next_attempt_at = datetime.now(UTC) + timedelta(seconds=error.retry_after)
                    item.scheduled_at = item.next_attempt_at
                except Exception as error:
                    item.attempts += 1
                    item.last_error = str(error)[:500]
                    item.status = (
                        NotificationStatus.FAILED
                        if item.attempts >= 10
                        else NotificationStatus.PENDING
                    )
                    item.next_attempt_at = datetime.now(UTC) + timedelta(
                        seconds=min(3600, 2 ** min(item.attempts, 10))
                    )
                    item.scheduled_at = item.next_attempt_at
                await session.commit()
    finally:
        await bot.session.close()
        await engine.dispose()
    return delivered


@celery_app.task(  # type: ignore[untyped-decorator]
    name="booking.deliver_notifications",
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def deliver_notifications_task() -> int:
    return asyncio.run(_deliver())
