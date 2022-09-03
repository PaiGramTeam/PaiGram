from typing import Optional

from playwright.async_api import Browser, Playwright, async_playwright

from core.service import Service
from utils.log import logger


class AioBrowser(Service):

    def __init__(self, loop=None):
        self.browser: Optional[Browser] = None
        self._playwright: Optional[Playwright] = None
        self._loop = loop

    async def start(self, *args, **kwargs):
        if self._playwright is None:
            logger.info("正在尝试启动 Playwright")
            self._playwright = await async_playwright().start()
            logger.success("Playwright 启动成功")
        if self.browser is None:
            logger.info("正在尝试启动 Browser")
            try:
                self.browser = await self._playwright.chromium.launch(timeout=5000)
                logger.success("启动 Browser 成功")
            except TimeoutError as err:
                logger.error("启动 Browser 失败")
                raise err

        return self.browser

    async def stop(self):
        if self.browser is not None:
            await self.browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def get_browser(self) -> Browser:
        if self.browser is None:
            raise RuntimeError("browser is not None")
        return self.browser
