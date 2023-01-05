"""BOT"""
import asyncio
import inspect
import os
import signal
from functools import wraps
from importlib import import_module
from inspect import Parameter, Signature
from signal import SIGABRT, SIGINT, SIGTERM, signal as signal_func
from ssl import SSLZeroReturnError
from typing import Callable, Dict, Generic, List, Optional, TYPE_CHECKING, Type, TypeVar

import pytz
import uvicorn
from async_timeout import timeout
from fastapi import FastAPI
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import AIORateLimiter, Application as TgApplication, Defaults
from telegram.request import HTTPXRequest
from typing_extensions import ParamSpec
from uvicorn import Server

from core.config import config as bot_config
from core.plugin import PluginType
from core.service import Service
from utils.const import PROJECT_ROOT, WRAPPER_ASSIGNMENTS
from utils.helpers import gen_pkg
from utils.log import logger
from utils.models.signal import Singleton

if TYPE_CHECKING:
    from core.executor import Executor
    from asyncio import AbstractEventLoop, CancelledError
    from types import FrameType

__all__ = ["Bot", "bot"]

R = TypeVar("R")
T = TypeVar("T")
P = ParamSpec("P")


class Control(Generic[T]):
    """控制类基类"""

    _lib: Dict[Type[T], T] = {}

    def _inject(self, signature: Signature, target: Callable[..., T]) -> T:
        kwargs = {}
        for name, parameter in signature.parameters.items():
            if name != "self" and parameter.annotation != Parameter.empty:
                if value := self._lib.get(parameter.annotation):
                    kwargs[name] = value
        return target(**kwargs)

    def init_inject(self, target: Callable[..., T]) -> T:
        if isinstance(target, type):
            signature = inspect.signature(target.__init__)
        else:
            signature = inspect.signature(target)
        return self._inject(signature, target)


class ServiceControl(Control):
    """服务控制类"""

    _services: Dict[Type[Service], Service] = {}

    @property
    def services(self) -> List[Service]:
        return list(self._services.values())

    @property
    def service_map(self) -> Dict[Type[Service], Service]:
        return self._services

    async def start_base_services(self):
        for pkg in gen_pkg(PROJECT_ROOT / "core/base"):
            try:
                import_module(pkg)
            except Exception as e:
                logger.exception(
                    '在导入文件 "%s" 的过程中遇到了错误 [red bold]%s[/]',
                    pkg,
                    type(e).__name__,
                    exc_info=e,
                    extra={"markup": True}
                )
                raise SystemExit from e
        for service_cls in Service.__subclasses__():
            try:
                if hasattr(service_cls, "from_config"):
                    instance = service_cls.from_config(bot_config)
                else:
                    instance = self.init_inject(service_cls)
                await instance.start()
                logger.success('服务 "%s" 初始化成功', service_cls.__name__)
                self._services.update({service_cls: instance})
            except Exception as e:
                logger.exception('服务 "%s" 初始化失败', service_cls.__name__)
                raise SystemExit from e

    async def start_services(self) -> None:
        await self.start_base_services()
        for path in (PROJECT_ROOT / "core").iterdir():
            if not path.name.startswith("_") and path.is_dir() and path.name != "base":
                pkg = str(path.relative_to(PROJECT_ROOT).with_suffix("")).replace(os.sep, ".")
                try:
                    import_module(pkg)
                except Exception as e:  # pylint: disable=W0703
                    logger.exception(
                        '在导入文件 "%s" 的过程中遇到了错误 [red bold]%s[/]',
                        pkg,
                        type(e).__name__,
                        exc_info=e,
                        extra={"markup": True},
                    )
                    continue

    async def stop_services(self):
        """关闭服务"""
        if not self._services:
            return
        logger.info("正在关闭服务")
        for _, service in filter(lambda x: not isinstance(x[1], TgApplication), self._services.items()):
            async with timeout(5):
                try:
                    if hasattr(service, "stop"):
                        if inspect.iscoroutinefunction(service.stop):
                            await service.stop()
                        else:
                            service.stop()
                        logger.success('服务 "%s" 关闭成功', service.__class__.__name__)
                except CancelledError:
                    logger.warning('服务 "%s" 关闭超时', service.__class__.__name__)
                except Exception as e:  # pylint: disable=W0703
                    logger.exception('服务 "%s" 关闭失败', service.__class__.__name__, exc_info=e)


class PluginControl(Control):
    """插件控制类"""

    _plugins: List[PluginType] = []

    @property
    def plugins(self) -> List[PluginType]:
        return self._plugins


class Bot(Singleton, ServiceControl, PluginControl):
    _tg_app: Optional[TgApplication] = None
    _web_server: "Server" = None
    _web_server_task: Optional[asyncio.Task] = None

    _executor: Optional["Executor"] = None

    _startup_funcs: List[Callable] = []
    _shutdown_funcs: List[Callable] = []

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
            await self.executor(func, block=getattr(func, "block", False))

    async def _on_shutdown(self) -> None:
        for func in self._shutdown_funcs:
            await self.executor(func, block=getattr(func, "block", False))

    async def initialize(self):
        """BOT 初始化"""
        await self.start_services()

    async def shutdown(self):
        """BOT 关闭"""
        await self.stop_services()

    async def start(self) -> None:
        """启动 BOT"""
        logger.info("正在启动 BOT 中...")
        self._running = True

        def error_callback(exc: TelegramError) -> None:
            self.tg_app.create_task(self.tg_app.process_error(error=exc, update=None))

        await self.initialize()
        logger.success("BOT 初始化成功")

        await self.tg_app.initialize()

        if not bot_config.webserver.close:
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
        self._running = False

        if self.tg_app.updater.running:
            await self.tg_app.updater.stop()

        await self._on_shutdown()

        if self.tg_app.running:
            await self.tg_app.stop()

        await self.tg_app.shutdown()
        if self._web_server is not None:
            await self._web_server.shutdown()

        await self.shutdown()
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
