import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Browser, Playwright

from logger import Log


class AioBrowser:
    def __init__(self, loop=None):
        self.browser: Optional[Browser] = None
        self._playwright: Optional[Playwright] = None
        self._loop = loop
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        try:
            Log.info("正在尝试启动Playwright")
            self._loop.run_until_complete(self._browser_init())
            Log.info("启动Playwright成功")
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as exc:
            Log.error("启动浏览器失败")
            raise exc

    async def _browser_init(self) -> Browser:
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            try:
                self.browser = await self._playwright.chromium.launch(timeout=5000)
            except TimeoutError as err:
                raise err
        else:
            if self.browser is None:
                try:
                    self.browser = await self._playwright.chromium.launch(timeout=10000)
                except TimeoutError as err:
                    raise err
        return self.browser

    async def close(self):
        if self.browser is not None:
            await self.browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def get_browser(self) -> Browser:
        if self.browser is None:
            raise RuntimeError("browser is not None")
        return self.browser
