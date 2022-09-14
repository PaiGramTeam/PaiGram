import asyncio

import fakeredis.aioredis
from redis import asyncio as aioredis
from typing_extensions import Self

from core.config import BotConfig
from core.service import Service
from utils.log import logger


class RedisDB(Service):
    @classmethod
    def from_config(cls, config: BotConfig) -> Self:
        return cls(**config.redis.dict())

    def __init__(self, host="127.0.0.1", port=6379, database=0, loop=None):
        self.client = aioredis.Redis(host=host, port=port, db=database)
        self.ttl = 600
        self.key_prefix = "paimon_bot"
        self._loop = loop

    async def ping(self):
        if await self.client.ping():
            logger.info("连接 [red]Redis[/] 成功", extra={'markup': True})
        else:
            logger.info("连接 [red]Redis[/] 失败", extra={'markup': True})
            raise RuntimeError("连接 Redis 失败")

    async def start(self):  # pylint: disable=W0221
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        logger.info("正在尝试建立与 [red]Redis[/] 连接", extra={'markup': True})
        try:
            await self.ping()
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as exc:
            logger.exception("尝试连接 [red]Redis[/] 失败，使用 [red]fakeredis[/] 模拟", exc_info=exc, extra={'markup': True})
            self.client = fakeredis.aioredis.FakeRedis()
            await self.ping()

    async def stop(self):  # pylint: disable=W0221
        await self.client.close()
