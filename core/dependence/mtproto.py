import os
from typing import Optional
from urllib.parse import urlparse

import aiofiles

from core.base_service import BaseService
from core.config import config as bot_config
from utils.log import logger

try:
    from pyrogram import Client
    from pyrogram.session import session

    session.log.debug = lambda *args, **kwargs: None  # 关闭日记
    PYROGRAM_AVAILABLE = True
except ImportError:
    Client = None
    session = None
    PYROGRAM_AVAILABLE = False


class MTProto(BaseService.Dependence):
    async def get_session(self):
        async with aiofiles.open(self.session_path, mode="r") as f:
            return await f.read()

    async def set_session(self, b: str):
        async with aiofiles.open(self.session_path, mode="w+") as f:
            await f.write(b)

    def session_exists(self):
        return os.path.exists(self.session_path)

    def __init__(self):
        self.name = "paigram"
        current_dir = os.getcwd()
        self.session_path = os.path.join(current_dir, "paigram.session")
        self.client: Optional[Client] = None
        self.proxy: Optional[dict] = None
        http_proxy = os.environ.get("HTTP_PROXY")
        if http_proxy is not None:
            http_proxy_url = urlparse(http_proxy)
            self.proxy = {"scheme": "http", "hostname": http_proxy_url.hostname, "port": http_proxy_url.port}

    async def initialize(self):  # pylint: disable=W0221
        if not PYROGRAM_AVAILABLE:
            logger.info("MTProto 服务需要的 pyrogram 模块未导入 本次服务 client 为 None")
            return
        if bot_config.mtproto.api_id is None:
            logger.info("MTProto 服务需要的 api_id 未配置 本次服务 client 为 None")
            return
        if bot_config.mtproto.api_hash is None:
            logger.info("MTProto 服务需要的 api_hash 未配置 本次服务 client 为 None")
            return
        self.client = Client(
            api_id=bot_config.mtproto.api_id,
            api_hash=bot_config.mtproto.api_hash,
            name=self.name,
            bot_token=bot_config.bot_token,
            proxy=self.proxy,
        )
        await self.client.start()

    async def shutdown(self):  # pylint: disable=W0221
        if self.client is not None:
            await self.client.stop(block=False)
