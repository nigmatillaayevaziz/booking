import hmac

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import Settings


def telegram_router(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["telegram"])

    @router.post("/webhooks/telegram", status_code=status.HTTP_200_OK)
    async def receive_update(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        expected = settings.telegram_webhook_secret.get_secret_value()
        if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
            x_telegram_bot_api_secret_token, expected
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")
        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": bot})
        await dispatcher.feed_update(bot, update)
        return {"ok": True}

    return router
