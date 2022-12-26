"""BOT"""
import asyncio
import signal
from functools import wraps
from signal import SIGABRT, SIGINT, SIGTERM, signal as signal_func
from ssl import SSLZeroReturnError
from typing import Callable, List, Optional, TYPE_CHECKING, TypeVar

import pytz
import uvicorn
from core.event import Event
from fastapi import FastAPI
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import AIORateLimiter, Application as TgApplication, Defaults
from telegram.request import HTTPXRequest
from typing_extensions import ParamSpec
from uvicorn import Server

from core.config import config as bot_config
from utils.const import WRAPPER_ASSIGNMENTS
from utils.log import logger
from utils.models.signal import Singleton

if TYPE_CHECKING:
    from core.executor import Executor
    from asyncio import AbstractEventLoop
    from types import FrameType

R = TypeVar("R")
T = TypeVar("T")
P = ParamSpec("P")


class Bot(Singleton):
    _tg_app: Optional[TgApplication] = None
    _web_server: "Server" = None
    _web_server_task: Optional[asyncio.Task] = None

    _executor: Optional["Executor"] = None

    _startup_funcs: List[Callable] = []
    _shutdown_funcs: List[Callable] = []
    _events: List[Event] = []

    _running: False

    @property
    def running(self) -> bool:
        """bot 是否正在运行"""
        with self._lock:
            return self._running

    @property
    def executor(self) -> "Executor":
        from core.executor import Executor

        with self._lock:
            if self._executor is None:
                self._executor = Executor("Bot")
        return self._executor

    @property
    def tg_app(self) -> TgApplication:
        """telegram app"""
        with self._lock:
            if self._tg_app is None:
                self._tg_app = (
                    TgApplication.builder()
                    .rate_limiter(AIORateLimiter())
                    .defaults(Defaults(tzinfo=pytz.timezone("Asia/Shanghai")))
                    .token(bot_config.bot_token)
                    .request(
                        HTTPXRequest(
                            256,
                            proxy_url=bot_config.proxy_url,
                            read_timeout=bot_config.read_timeout,
                            write_timeout=bot_config.write_timeout,
                            connect_timeout=bot_config.connect_timeout,
                            pool_timeout=bot_config.pool_timeout,
                        )
                    )
                    .build()
                )
        return self._tg_app

    @property
    def web_app(self) -> FastAPI:
        """fastapi app"""
        return self.web_server.config.app

    @property
    def web_server(self) -> Server:
        """uvicorn server"""
        with self._lock:
            if self._web_server is None:
                from uvicorn import Server

                self._web_server = Server(
                    uvicorn.Config(
                        app=FastAPI(debug=bot_config.debug),
                        port=bot_config.webserver.port,
                        host=bot_config.webserver.host,
                        log_config=None,
                    )
                )
        return self._web_server

    def __init__(self) -> None:
        self._running = False

    async def _on_startup(self) -> None:
        for func in self._startup_funcs:
            await self.executor(func, block=getattr(func, "block", False), args=[self])

    async def _on_shutdown(self) -> None:
        for func in self._shutdown_funcs:
            await self.executor(func, block=getattr(func, "block", False), args=[self])

    async def initialize(self):
        """BOT 初始化"""

    async def shutdown(self):
        """BOT 关闭"""

    async def start(self) -> None:
        """启动 BOT"""
        logger.info("正在启动 BOT 中...")

        def error_callback(exc: TelegramError) -> None:
            self.tg_app.create_task(self.tg_app.process_error(error=exc, update=None))

        await self.initialize()
        logger.success("BOT 初始化成功")

        await self.tg_app.initialize()

        server_config = self.web_server.config
        server_config.setup_event_loop()
        if not server_config.loaded:
            server_config.load()
        self.web_server.lifespan = server_config.lifespan_class(server_config)
        await self.web_server.startup()
        if self.web_server.should_exit:
            logger.error("web server 启动失败，正在退出")
            raise SystemExit

        self._web_server_task = asyncio.create_task(self.web_server.main_loop())

        for _ in range(5):  # 连接至 telegram 服务器
            try:
                await self.tg_app.updater.start_polling(error_callback=error_callback)
                break
            except TimedOut:
                logger.warning("连接至 [blue]telegram[/] 服务器失败，正在重试", extra={"markup": True})
                continue
            except NetworkError as e:
                logger.exception()
                if isinstance(e, SSLZeroReturnError):
                    logger.error("代理服务出现异常, 请检查您的代理服务是否配置成功.")
                else:
                    logger.error("网络连接出现问题, 请检查您的网络状况.")
                raise SystemExit

        await self._on_startup()
        await self.tg_app.start()
        self._running = True
        logger.success("BOT 启动成功")

    # noinspection PyUnusedLocal
    def stop_signal_handler(self, signum: int, frame: "FrameType"):
        signals = {k: v for v, k in signal.__dict__.items() if v.startswith("SIG") and not v.startswith("SIG_")}
        logger.debug(f"接收到了终止信号 {signals[signum]} 正在退出...")
        self._web_server_task.cancel()

    async def idle(self) -> None:
        """在接收到中止信号之前，堵塞loop"""

        task = None

        def stop_handler(signum, frame) -> None:
            self.stop_signal_handler(signum, frame)
            task.cancel()

        for s in (SIGINT, SIGTERM, SIGABRT):
            signal_func(s, stop_handler)

        while True:
            task = asyncio.create_task(asyncio.sleep(600))

            try:
                await task
            except asyncio.CancelledError:
                break

    async def stop(self):
        """关闭"""
        logger.info("BOT 正在关闭")

        if self.tg_app.updater.running:
            await self.tg_app.updater.stop()

        await self._on_shutdown()

        if self.tg_app.running:
            await self.tg_app.stop()

        await self.tg_app.shutdown()
        if self._web_server is not None:
            await self._web_server.shutdown()

        await self.shutdown()
        self._running = False
        logger.success("BOT 关闭成功")

    def launch(self):
        """启动"""
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.start())
            loop.run_until_complete(self.idle())
        except (SystemExit, KeyboardInterrupt):
            pass  # 接收到了终止信号
        except NetworkError as e:
            if isinstance(e, SSLZeroReturnError):
                logger.error("代理服务出现异常, 请检查您的代理服务是否配置成功.")
            else:
                logger.error("网络连接出现问题, 请检查您的网络状况.")
        except Exception as e:
            logger.exception(f"遇到了未知错误: {type(e)}")
        finally:
            loop.run_until_complete(self.stop())
            raise SystemExit

    # decorators

    def on_startup(self, func: Callable[P, R]) -> Callable[P, R]:
        """注册一个在 BOT 启动时执行的函数"""

        if func not in self._startup_funcs:
            self._startup_funcs.append(func)

        # noinspection PyTypeChecker
        @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        return wrapper

    def on_shutdown(self, func: Callable[P, R]) -> Callable[P, R]:
        """注册一个在 BOT 停止时执行的函数"""

        if func not in self._shutdown_funcs:
            self._shutdown_funcs.append(func)

        # noinspection PyTypeChecker
        @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        return wrapper


bot = Bot()
