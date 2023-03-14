"""BOT"""
import asyncio
import signal
from functools import wraps
from signal import SIGABRT, SIGINT, SIGTERM, signal as signal_func
from ssl import SSLZeroReturnError
from typing import Callable, List, Optional, TYPE_CHECKING, TypeVar

import pytz
import uvicorn
from fastapi import FastAPI
from telegram import Bot, Update
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import (
    Application as TelegramApplication,
    ApplicationBuilder as TelegramApplicationBuilder,
    Defaults,
    JobQueue,
)
from typing_extensions import ParamSpec
from uvicorn import Server

from core.config import config as application_config
from core.handler.limiterhandler import LimiterHandler
from core.manager import Managers
from core.override.telegram import HTTPXRequest
from utils.const import WRAPPER_ASSIGNMENTS
from utils.log import logger
from utils.models.signal import Singleton

if TYPE_CHECKING:
    from asyncio import Task
    from types import FrameType

__all__ = ("Application",)

R = TypeVar("R")
T = TypeVar("T")
P = ParamSpec("P")


class Application(Singleton):
    """Application"""

    _web_server_task: Optional["Task"] = None

    _startup_funcs: List[Callable] = []
    _shutdown_funcs: List[Callable] = []

    def __init__(self, managers: "Managers", telegram: "TelegramApplication", web_server: "Server") -> None:
        self._running = False
        self.managers = managers
        self.telegram = telegram
        self.web_server = web_server
        self.managers.set_application(application=self)  # 给 managers 设置 application
        self.managers.build_executor("Application")

    @classmethod
    def build(cls):
        managers = Managers()
        telegram = (
            TelegramApplicationBuilder()
            .get_updates_read_timeout(application_config.update_read_timeout)
            .get_updates_write_timeout(application_config.update_write_timeout)
            .get_updates_connect_timeout(application_config.update_connect_timeout)
            .get_updates_pool_timeout(application_config.update_pool_timeout)
            .defaults(Defaults(tzinfo=pytz.timezone("Asia/Shanghai")))
            .token(application_config.bot_token)
            .request(
                HTTPXRequest(
                    connection_pool_size=application_config.connection_pool_size,
                    proxy_url=application_config.proxy_url,
                    read_timeout=application_config.read_timeout,
                    write_timeout=application_config.write_timeout,
                    connect_timeout=application_config.connect_timeout,
                    pool_timeout=application_config.pool_timeout,
                )
            )
            .build()
        )
        web_server = Server(
            uvicorn.Config(
                app=FastAPI(debug=application_config.debug),
                port=application_config.webserver.port,
                host=application_config.webserver.host,
                log_config=None,
            )
        )
        return cls(managers, telegram, web_server)

    @property
    def running(self) -> bool:
        """bot 是否正在运行"""
        with self._lock:
            return self._running

    @property
    def web_app(self) -> FastAPI:
        """fastapi app"""
        return self.web_server.config.app

    @property
    def bot(self) -> Optional[Bot]:
        return self.telegram.bot

    @property
    def job_queue(self) -> Optional[JobQueue]:
        return self.telegram.job_queue

    async def _on_startup(self) -> None:
        for func in self._startup_funcs:
            await self.managers.executor(func, block=getattr(func, "block", False))

    async def _on_shutdown(self) -> None:
        for func in self._shutdown_funcs:
            await self.managers.executor(func, block=getattr(func, "block", False))

    async def initialize(self):
        """BOT 初始化"""
        self.telegram.add_handler(LimiterHandler(limit_time=10), group=-1)  # 启用入口洪水限制
        await self.managers.start_dependency()  # 启动基础服务
        await self.managers.init_components()  # 实例化组件
        await self.managers.start_services()  # 启动其他服务
        await self.managers.install_plugins()  # 安装插件

    async def shutdown(self):
        """BOT 关闭"""
        await self.managers.uninstall_plugins()  # 卸载插件
        await self.managers.stop_services()  # 终止其他服务
        await self.managers.stop_dependency()  # 终止基础服务

    async def start(self) -> None:
        """启动 BOT"""
        logger.info("正在启动 BOT 中...")

        def error_callback(exc: TelegramError) -> None:
            """错误信息回调"""
            self.telegram.create_task(self.telegram.process_error(error=exc, update=None))

        await self.telegram.initialize()
        logger.info("[blue]Telegram[/] 初始化成功", extra={"markup": True})

        if application_config.webserver.enable:  # 如果使用 web app
            server_config = self.web_server.config
            server_config.setup_event_loop()
            if not server_config.loaded:
                server_config.load()
            self.web_server.lifespan = server_config.lifespan_class(server_config)
            try:
                await self.web_server.startup()
            except OSError as e:
                if e.errno == 10048:
                    logger.error("Web Server 端口被占用：%s", e)
                logger.error("Web Server 启动失败，正在退出")
                raise SystemExit from None

            if self.web_server.should_exit:
                logger.error("Web Server 启动失败，正在退出")
                raise SystemExit from None
            logger.success("Web Server 启动成功")

            self._web_server_task = asyncio.create_task(self.web_server.main_loop())

        for _ in range(5):  # 连接至 telegram 服务器
            try:
                await self.telegram.updater.start_polling(
                    error_callback=error_callback, allowed_updates=Update.ALL_TYPES
                )
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
                raise SystemExit from e

        await self.initialize()
        logger.success("BOT 初始化成功")
        logger.debug("BOT 开始启动")

        await self._on_startup()
        await self.telegram.start()
        self._running = True
        logger.success("BOT 启动成功")

    def stop_signal_handler(self, signum: int):
        """终止信号处理"""
        signals = {k: v for v, k in signal.__dict__.items() if v.startswith("SIG") and not v.startswith("SIG_")}
        logger.debug("接收到了终止信号 %s 正在退出...", signals[signum])
        if self._web_server_task:
            self._web_server_task.cancel()

    async def idle(self) -> None:
        """在接收到中止信号之前，堵塞loop"""

        task = None

        def stop_handler(signum: int, _: "FrameType") -> None:
            self.stop_signal_handler(signum)
            task.cancel()

        for s in (SIGINT, SIGTERM, SIGABRT):
            signal_func(s, stop_handler)

        while True:
            task = asyncio.create_task(asyncio.sleep(600))

            try:
                await task
            except asyncio.CancelledError:
                break

    async def stop(self) -> None:
        """关闭"""
        logger.info("BOT 正在关闭")
        self._running = False

        await self._on_shutdown()

        if self.telegram.updater.running:
            await self.telegram.updater.stop()

        await self.shutdown()

        if self.telegram.running:
            await self.telegram.stop()

        await self.telegram.shutdown()
        if self.web_server is not None:
            try:
                await self.web_server.shutdown()
                logger.info("Web Server 已经关闭")
            except AttributeError:
                pass

        logger.success("BOT 关闭成功")

    def launch(self) -> None:
        """启动"""
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.start())
            loop.run_until_complete(self.idle())
        except (SystemExit, KeyboardInterrupt) as exc:
            logger.debug("接收到了终止信号，BOT 即将关闭", exc_info=exc)  # 接收到了终止信号
        except NetworkError as e:
            if isinstance(e, SSLZeroReturnError):
                logger.critical("代理服务出现异常, 请检查您的代理服务是否配置成功.")
            else:
                logger.critical("网络连接出现问题, 请检查您的网络状况.")
        except Exception as e:
            logger.critical("遇到了未知错误: %s", {type(e)}, exc_info=e)
        finally:
            loop.run_until_complete(self.stop())

            if application_config.reload:
                raise SystemExit from None

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
