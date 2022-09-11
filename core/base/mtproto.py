import os
from typing import Optional
from urllib.parse import urlparse

import aiofiles

from utils.log import logger

try:
    from pyrogram import Client
    from pyrogram.session import session

    session.log.debug = lambda *args, **kwargs: None  # 关闭日记
    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False

from core.bot import bot
from core.service import Service


class MTProto(Service):

    async def get_session(self):
        async with aiofiles.open(self.session_path, mode='r') as f:
            return await f.read()

    async def set_session(self, b: str):
        async with aiofiles.open(self.session_path, mode='w+') as f:
            await f.write(b)

    def session_exists(self):
        return os.path.exists(self.session_path)

    def __init__(self):
        self.name = "TGPaimonBot"
        current_dir = os.getcwd()
        self.session_path = os.path.join(current_dir, "paimon.session")
        self.client: Optional[Client] = None
        self.proxy: Optional[dict] = None
        http_proxy = os.environ.get("HTTP_PROXY")
        if http_proxy is not None:
            http_proxy_url = urlparse(http_proxy)
            self.proxy = {"scheme": "http", "hostname": http_proxy_url.hostname, "port": http_proxy_url.port}

    async def start(self):  # pylint: disable=W0221
        if not PYROGRAM_AVAILABLE:
            logger.warning("MTProto 服务需要的 pyrogram 模块未导入 本次服务 client 为 None")
            return
        if bot.config.mtproto.api_id is None:
            logger.warning("MTProto 服务需要的 api_id 未配置 本次服务 client 为 None")
            return
        if bot.config.mtproto.api_hash is None:
            logger.warning("MTProto 服务需要的 api_hash 未配置 本次服务 client 为 None")
            return
        if self.session_exists():
            session_string = await self.get_session()
            self.client = Client(api_id=bot.config.mtproto.api_id, api_hash=bot.config.mtproto.api_hash, name=self.name,
                                 bot_token=bot.config.bot_token, session_string=session_string, proxy=self.proxy)
        else:
            self.client = Client(api_id=bot.config.mtproto.api_id, api_hash=bot.config.mtproto.api_hash, name=self.name,
                                 bot_token=bot.config.bot_token, in_memory=True, proxy=self.proxy)
        await self.client.start()
        session_string = await self.client.export_session_string()
        await self.set_session(session_string)

    async def stop(self):  # pylint: disable=W0221
        if self.client is not None:
            await self.client.stop(block=False)
