from typing import Optional, TYPE_CHECKING

from playwright.async_api import Error, async_playwright

from core.base_service import BaseService
from utils.log import logger

if TYPE_CHECKING:
    from playwright.async_api import Playwright as AsyncPlaywright, Browser

__all__ = ("AioBrowser",)


class AioBrowser(BaseService.Dependence):
    @property
    def browser(self):
        return self._browser

    def __init__(self, loop=None):
        self._browser: Optional["Browser"] = None
        self._playwright: Optional["AsyncPlaywright"] = None
        self._loop = loop

    async def get_browser(self):
        if self._browser is None:
            await self.initialize()
        return self._browser

    async def initialize(self):
        if self._playwright is None:
            logger.info("正在尝试启动 [blue]Playwright[/]", extra={"markup": True})
            self._playwright = await async_playwright().start()
            logger.success("[blue]Playwright[/] 启动成功", extra={"markup": True})
        if self._browser is None:
            logger.info("正在尝试启动 [blue]Browser[/]", extra={"markup": True})
            try:
                self._browser = await self._playwright.chromium.launch(timeout=5000)
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

        return self._browser

    async def shutdown(self):
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
