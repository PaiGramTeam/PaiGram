from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Optional, Type

import httpx

__all__ = ("HTTPXRequest",)


class HTTPXRequest(AbstractAsyncContextManager):
    def __init__(self, *args, headers=None, **kwargs):
        self._client = httpx.AsyncClient(headers=headers, *args, **kwargs)

    async def __aenter__(self):
        try:
            await self.initialize()
            return self
        except Exception as exc:
            await self.shutdown()
            raise exc

    async def __aexit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        await self.initialize()

    async def initialize(self):
        if self._client.is_closed:
            self._client = httpx.AsyncClient()

    async def shutdown(self):
        if self._client.is_closed:
            return
        await self._client.aclose()
