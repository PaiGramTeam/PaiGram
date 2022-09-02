import asyncio

import fakeredis.aioredis
from redis import asyncio as aioredis
from typing_extensions import Self

from core.config import AppConfig
from core.service import Service
from utils.log import logger


class RedisDB(Service):
    @classmethod
    def from_config(cls, config: AppConfig) -> Self:
        return cls(**config.redis.dict())

    def __init__(self, host="127.0.0.1", port=6379, database=0, loop=None):
        logger.debug(f'获取Redis配置 [host]: {host}')
        logger.debug(f'获取Redis配置 [port]: {port}')
        logger.debug(f'获取Redis配置 [db]: {database}')
        self.client = aioredis.Redis(host=host, port=port, db=database)
        self.ttl = 600
        self.key_prefix = "paimon_bot"
        self._loop = loop

    async def ping(self):
        if await self.client.ping():
            logger.info("连接Redis成功")
        else:
            logger.info("连接Redis失败")
            raise RuntimeError("连接Redis失败")

    async def start(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        logger.info("正在尝试建立与Redis连接")
        try:
            await self.ping()
        except (KeyboardInterrupt, SystemExit):
            pass
        except BaseException as exc:
            logger.warning("尝试连接Redis失败，使用 fakeredis 模拟", exc)
            self.client = fakeredis.aioredis.FakeRedis()
            await self.ping()

    async def stop(self):
        await self.client.close()
