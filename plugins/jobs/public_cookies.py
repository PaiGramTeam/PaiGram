import asyncio
import datetime

from telegram.ext import CallbackContext

from core.plugin import Plugin, job
from core.services.cookies import PublicCookiesService
from utils.log import logger


class PublicCookies(Plugin):
    def __init__(self, public_cookies_service: PublicCookiesService = None):
        self.public_cookies_service = public_cookies_service

    async def __async_init__(self):
        async def _refresh():
            logger.info("正在刷新公共Cookies池")
            await self.public_cookies_service.refresh()
            logger.success("刷新公共Cookies池成功")

        asyncio.create_task(_refresh())

    @job.run_repeating(interval=datetime.timedelta(hours=2), name="PublicCookiesRefresh")
    async def refresh(self, _: CallbackContext):
        logger.info("正在刷新公共Cookies池")
        await self.public_cookies_service.refresh()
        logger.success("刷新公共Cookies池成功")
