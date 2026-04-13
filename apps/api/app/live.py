from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from redis.asyncio import Redis

from .config import get_settings

settings = get_settings()


async def live_messages() -> AsyncIterator[str]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(settings.live_channel)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
            if message and message.get("data"):
                yield str(message["data"])
            else:
                yield json.dumps({"topic": "heartbeat", "action": "upsert", "payload": {"at": asyncio.get_running_loop().time()}})
    finally:
        await pubsub.unsubscribe(settings.live_channel)
        await pubsub.aclose()
        await redis.aclose()
