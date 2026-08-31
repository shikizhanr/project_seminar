import json

from redis.asyncio import Redis

from backend.app.core.config import settings

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=0.2,
    socket_timeout=0.2,
)


async def cache_get(key: str) -> dict | None:
    try:
        value = await redis_client.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


async def cache_set(key: str, value: dict, ttl: int = 60) -> None:
    try:
        await redis_client.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass


async def cache_delete(key: str) -> None:
    try:
        await redis_client.delete(key)
    except Exception:
        pass
