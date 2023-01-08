import asyncio
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI
from typing_extensions import Self

from core.base_service import BaseService
from core.config import config as bot_config

if TYPE_CHECKING:
    from core.config import BotConfig

__all__ = ("webapp", "WebServer")

webapp = FastAPI(debug=bot_config.debug)


@webapp.get("/")
def index():
    return {"Hello": "Paimon"}


class WebServer(BaseService.Dependence):
    debug: bool

    host: str
    port: int

    server: uvicorn.Server

    _server_task: asyncio.Task

    @classmethod
    def from_config(cls, config: "BotConfig") -> Self:
        return cls(debug=config.debug, host=config.webserver.host, port=config.webserver.port)

    def __init__(self, debug: bool, host: str, port: int):
        self.debug = debug
        self.host = host
        self.port = port

        self.server = uvicorn.Server(
            uvicorn.Config(app=webapp, port=port, use_colors=False, host=host, log_config=None)
        )

    async def initialize(self):
        """启动 service"""

        # 暂时只在开发环境启动 webserver 用于开发调试
        if not self.debug:
            return

        # 防止 uvicorn server 拦截 signals
        self.server.install_signal_handlers = lambda: None
        self._server_task = asyncio.create_task(self.server.serve())

    async def shutdown(self):
        """关闭 service"""
        if not self.debug:
            return

        self.server.should_exit = True

        # 等待 task 结束
        await self._server_task
