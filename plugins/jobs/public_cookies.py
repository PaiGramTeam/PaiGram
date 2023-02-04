import datetime

from telegram.ext import CallbackContext

from core.plugin import Plugin, job
from core.services.cookies.services import PublicCookiesService
from utils.log import logger

__all__ = ("PublicCookiesPlugin",)


class PublicCookiesPlugin(Plugin):
    def __init__(self, public_cookies_service: PublicCookiesService = None):
        self.public_cookies_service = public_cookies_service

    @job.run_repeating(interval=datetime.timedelta(hours=2), name="PublicCookiesRefresh")
    async def refresh(self, _: CallbackContext):
        logger.info("正在刷新公共Cookies池")
        await self.public_cookies_service.refresh()
        logger.success("刷新公共Cookies池成功")
