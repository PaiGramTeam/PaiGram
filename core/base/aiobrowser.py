from typing import Optional

from playwright.async_api import Browser, Error, Playwright, async_playwright

from core.service import Service
from utils.log import logger


class AioBrowser(Service):
    def __init__(self, loop=None):
        self.browser: Optional[Browser] = None
        self._playwright: Optional[Playwright] = None
        self._loop = loop

    async def start(self):
        if self._playwright is None:
            logger.info("正在尝试启动 [blue]Playwright[/]", extra={"markup": True})
            self._playwright = await async_playwright().start()
            logger.success("[blue]Playwright[/] 启动成功", extra={"markup": True})
        if self.browser is None:
            logger.info("正在尝试启动 [blue]Browser[/]", extra={"markup": True})
            try:
                self.browser = await self._playwright.chromium.launch(timeout=5000)
                logger.success("[blue]Browser[/] 启动成功", extra={"markup": True})
            except Error as err:
                if "playwright install" in str(err):
                    logger.error(
                        "检查到 [blue]playwright[/] 刚刚安装或者未升级\n"
                        "请运行以下命令下载新浏览器\n"
                        "[blue bold]playwright install chromium[/]",
                        extra={"markup": True},
                    )
                    raise RuntimeError("检查到 playwright 刚刚安装或者未升级\n请运行以下命令下载新浏览器\nplaywright install chromium")
                raise err

        return self.browser

    async def stop(self):
        if self.browser is not None:
            await self.browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def get_browser(self) -> Browser:
        if self.browser is None:
            await self.start()
        return self.browser
