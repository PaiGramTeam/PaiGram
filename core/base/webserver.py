import asyncio

import uvicorn
from fastapi import FastAPI

from core.config import BotConfig, config as botConfig
from core.service import Service

__all__ = ["webapp", "WebServer"]

webapp = FastAPI(debug=botConfig.debug)


@webapp.get("/")
def index():
    return {"Hello": "Paimon"}


class WebServer(Service):
    debug: bool

    host: str
    port: int

    server: uvicorn.Server

    _server_task: asyncio.Task

    @classmethod
    def from_config(cls, config: BotConfig) -> Service:
        return cls(debug=config.debug, **config.webserver.dict())

    def __init__(self, debug: bool, host: str, port: int):
        self.debug = debug
        self.host = host
        self.port = port

        self.server = uvicorn.Server(
            uvicorn.Config(
                app=webapp,
                port=port,
                use_colors=False,
                host=host,
                log_config=None,
            )
        )

    async def start(self):
        """启动 service"""

        # 暂时只在开发环境启动 webserver 用于开发调试
        if not self.debug:
            return

        # 防止 uvicorn server 拦截 signals
        self.server.install_signal_handlers = lambda: None
        self._server_task = asyncio.create_task(self.server.serve())

    async def stop(self):
        """关闭 service"""
        if not self.debug:
            return

        self.server.should_exit = True

        # 等待 task 结束
        await self._server_task
