from asyncio import AbstractEventLoop

from playwright.async_api import Browser, Playwright as AsyncPlaywright

from core.base_service import BaseService

__all__ = ("AioBrowser",)

class AioBrowser(BaseService.Dependence):
    _browser: Browser | None
    _playwright: AsyncPlaywright | None
    _loop: AbstractEventLoop

    @property
    def browser(self) -> Browser | None: ...
    async def get_browser(self) -> Browser: ...
