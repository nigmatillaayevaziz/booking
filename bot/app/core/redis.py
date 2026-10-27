from redis.asyncio import Redis

from app.core.config import get_settings

redis = Redis.from_url(get_settings().redis_url.get_secret_value(), decode_responses=True)
