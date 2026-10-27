from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import sentry_sdk
import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI, Request
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings
from app.core.context import begin_request, end_request
from app.core.db import engine
from app.core.logging import configure_logging
from app.core.redis import redis
from app.handlers import register_routers
from app.middlewares.rate_limit import RateLimitMiddleware
from app.webhooks.telegram import telegram_router

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)

bot = Bot(
    token=settings.bot_token.get_secret_value(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dispatcher = Dispatcher(
    storage=RedisStorage(
        redis=redis,
        state_ttl=timedelta(hours=24),
        data_ttl=timedelta(hours=24),
    )
)
dispatcher.update.outer_middleware(RateLimitMiddleware(redis))
register_routers(dispatcher)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await bot.set_webhook(
        settings.webhook_url,
        secret_token=settings.telegram_webhook_secret.get_secret_value(),
        allowed_updates=dispatcher.resolve_used_update_types(),
    )
    logger.info("application_started", environment=settings.environment)
    yield
    await bot.session.close()
    await redis.aclose()
    await engine.dispose()
    logger.info("application_stopped")


app = FastAPI(title="UzBooking Bot", version="0.1.0", lifespan=lifespan)
app.include_router(telegram_router(bot, dispatcher, settings))


@app.middleware("http")
async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
    token = begin_request(request.headers.get("X-Request-ID"))
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = token.var.get()
        return response
    finally:
        end_request(token)


@app.get("/health/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def ready() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ready"}
