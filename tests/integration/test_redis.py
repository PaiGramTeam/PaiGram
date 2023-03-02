from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from core.dependence.redisdb import RedisDB


@pytest.mark.asyncio
async def test_mysql(redis: "RedisDB"):
    assert redis
    assert redis.client


async def test_redis_ping(redis: "RedisDB"):
    await redis.ping()
