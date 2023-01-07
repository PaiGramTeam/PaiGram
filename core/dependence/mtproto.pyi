from __future__ import annotations
from typing import TypedDict

from core.base_service import BaseService

try:
    from pyrogram import Client
    from pyrogram.session import session

    PYROGRAM_AVAILABLE = True
except ImportError:
    Client = None
    session = None
    PYROGRAM_AVAILABLE = False

__all__ = ("MTProto",)

class _ProxyType(TypedDict):
    scheme: str
    hostname: str | None
    port: int | None

class MTProto(BaseService.Dependence):
    name: str
    session_path: str
    client: Client | None
    proxy: _ProxyType | None

    async def get_session(self) -> str: ...
    async def set_session(self, b: str) -> None: ...
    def session_exists(self) -> bool: ...
