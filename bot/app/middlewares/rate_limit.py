from collections.abc import Awaitable, Callable
from typing import Any, cast

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, limit: int = 3, window_seconds: int = 1) -> None:
        self.redis = redis
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        key = f"rate:user:{user.id}"
        script = """
        local count = redis.call('INCR', KEYS[1])
        if count == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        return count
        """
        result = self.redis.eval(script, 1, key, str(self.window_seconds))
        count = int(await cast(Awaitable[str], result))
        if count > self.limit:
            return None
        return await handler(event, data)
