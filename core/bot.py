import asyncio
import inspect
import os
from asyncio import CancelledError
from importlib import import_module
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterator, List, NoReturn, Optional, TYPE_CHECKING, Type, TypeVar

import genshin
import pytz
from async_timeout import timeout
from telegram import Update
from telegram import __version__ as tg_version
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    AIORateLimiter,
    Application as TgApplication,
    CallbackContext,
    Defaults,
    JobQueue,
    MessageHandler,
    filters,
    TypeHandler,
)
from telegram.ext.filters import StatusUpdate

from core.config import BotConfig, config  # pylint: disable=W0611
from core.error import ServiceNotFoundError

# noinspection PyProtectedMember
from core.plugin import Plugin, _Plugin
from core.service import Service
from metadata.scripts.metadatas import make_github_fast
from utils.const import PLUGIN_DIR, PROJECT_ROOT
from utils.log import logger


__all__ = ["bot"]

T = TypeVar("T")
PluginType = TypeVar("PluginType", bound=_Plugin)

try:
    from telegram import __version_info__ as tg_version_info
except ImportError:
    tg_version_info = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if tg_version_info < (20, 0, 0, "alpha", 6):
    logger.warning(
        "Bot与当前PTB版本 [cyan bold]%s[/] [red bold]不兼容[/]，请更新到最新版本后使用 [blue bold]poetry install[/] 重新安装依赖",
        tg_version,
        extra={"markup": True},
    )


class Bot:
    _lock: ClassVar[Lock] = Lock()
    _instance: ClassVar[Optional["Bot"]] = None

    def __new__(cls, *args, **kwargs) -> "Bot":
        """实现单例"""
        with cls._lock:  # 使线程、进程安全
            if cls._instance is None:
                cls._instance = object.__new__(cls)
        return cls._instance

    app: Optional[TgApplication] = None
    _config: BotConfig = config
    _services: Dict[Type[T], T] = {}
    _running: bool = False

    def _inject(self, signature: inspect.Signature, target: Callable[..., T]) -> T:
        kwargs = {}
        for name, parameter in signature.parameters.items():
            if name != "self" and parameter.annotation != inspect.Parameter.empty:
                if value := self._services.get(parameter.annotation):
                    kwargs[name] = value
        return target(**kwargs)

    def init_inject(self, target: Callable[..., T]) -> T:
        """用于实例化Plugin的方法。用于给插件传入一些必要组件，如 MySQL、Redis等"""
        if isinstance(target, type):
            signature = inspect.signature(target.__init__)
        else:
            signature = inspect.signature(target)
        return self._inject(signature, target)

    async def async_inject(self, target: Callable[..., T]) -> T:
        return await self._inject(inspect.signature(target), target)

    def _gen_pkg(self, root: Path) -> Iterator[str]:
        """生成可以用于 import_module 导入的字符串"""
        for path in root.iterdir():
            if not path.name.startswith("_"):
                if path.is_dir():
                    yield from self._gen_pkg(path)
                elif path.suffix == ".py":
                    yield str(path.relative_to(PROJECT_ROOT).with_suffix("")).replace(os.sep, ".")

    async def install_plugins(self):
        """安装插件"""
        for pkg in self._gen_pkg(PLUGIN_DIR):
            try:
                import_module(pkg)  # 导入插件
            except Exception as e:  # pylint: disable=W0703
                logger.exception(
                    '在导入文件 "%s" 的过程中遇到了错误 [red bold]%s[/]', pkg, type(e).__name__, exc_info=e, extra={"markup": True}
                )
                continue  # 如有错误则继续
        callback_dict: Dict[int, List[Callable]] = {}
        for plugin_cls in {*Plugin.__subclasses__(), *Plugin.Conversation.__subclasses__()}:
            path = f"{plugin_cls.__module__}.{plugin_cls.__name__}"
            try:
                plugin: PluginType = self.init_inject(plugin_cls)
                if hasattr(plugin, "__async_init__"):
                    await self.async_inject(plugin.__async_init__)
                handlers = plugin.handlers
                for index, handler in enumerate(handlers):
                    if isinstance(handler, TypeHandler):  # 对 TypeHandler 进行特殊处理，优先级必须设置 -1，否则无用
                        handlers.pop(index)
                        self.app.add_handler(handler, group=-1)
                self.app.add_handlers(handlers)
                if handlers:
                    logger.debug('插件 "%s" 添加了 %s 个 handler ', path, len(handlers))

                # noinspection PyProtectedMember
                for priority, callback in plugin._new_chat_members_handler_funcs():  # pylint: disable=W0212
                    if not callback_dict.get(priority):
                        callback_dict[priority] = []
                    callback_dict[priority].append(callback)

                error_handlers = plugin.error_handlers
                for callback, block in error_handlers.items():
                    self.app.add_error_handler(callback, block)
                if error_handlers:
                    logger.debug('插件 "%s" 添加了 %s 个 error handler ', path, len(error_handlers))

                if jobs := plugin.jobs:
                    logger.debug('插件 "%s" 添加了 %s 个 jobs ', path, len(jobs))
                logger.success('插件 "%s" 载入成功', path)
            except Exception as e:  # pylint: disable=W0703
                logger.exception(
                    '在安装插件 "%s" 的过程中遇到了错误 [red bold]%s[/]', path, type(e).__name__, exc_info=e, extra={"markup": True}
                )
        if callback_dict:
            num = sum(len(callback_dict[i]) for i in callback_dict)

            async def _new_chat_member_callback(update: "Update", context: "CallbackContext"):
                nonlocal callback
                for _, value in callback_dict.items():
                    for callback in value:
                        await callback(update, context)

            self.app.add_handler(
                MessageHandler(callback=_new_chat_member_callback, filters=StatusUpdate.NEW_CHAT_MEMBERS, block=False)
            )
            logger.success(
                "成功添加了 %s 个针对 [blue]%s[/] 的 [blue]MessageHandler[/]",
                num,
                StatusUpdate.NEW_CHAT_MEMBERS,
                extra={"markup": True},
            )
        # special handler
        from plugins.system.start import StartPlugin

        self.app.add_handler(
            MessageHandler(
                callback=StartPlugin.unknown_command, filters=filters.COMMAND & filters.ChatType.PRIVATE, block=False
            )
        )

    async def _start_base_services(self):
        for pkg in self._gen_pkg(PROJECT_ROOT / "core/base"):
            try:
                import_module(pkg)
            except Exception as e:  # pylint: disable=W0703
                logger.exception(
                    '在导入文件 "%s" 的过程中遇到了错误 [red bold]%s[/]', pkg, type(e).__name__, exc_info=e, extra={"markup": True}
                )
                raise SystemExit from e
        for base_service_cls in Service.__subclasses__():
            try:
                if hasattr(base_service_cls, "from_config"):
                    instance = base_service_cls.from_config(self._config)
                else:
                    instance = self.init_inject(base_service_cls)
                await instance.start()
                logger.success('服务 "%s" 初始化成功', base_service_cls.__name__)
                self._services.update({base_service_cls: instance})
            except Exception as e:
                logger.error('服务 "%s" 初始化失败', base_service_cls.__name__)
                raise SystemExit from e

    async def start_services(self):
        """启动服务"""
        await self._start_base_services()
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

    async def _post_init(self, context: CallbackContext) -> NoReturn:
        logger.info("开始初始化 genshin.py 相关资源")
        try:
            # 替换为 fastgit 镜像源
            for i in dir(genshin.utility.extdb):
                if "_URL" in i:
                    setattr(
                        genshin.utility.extdb,
                        i,
                        make_github_fast(getattr(genshin.utility.extdb, i)),
                    )
            await genshin.utility.update_characters_enka()
        except Exception as exc:  # pylint: disable=W0703
            logger.error("初始化 genshin.py 相关资源失败")
            logger.exception(exc)
        else:
            logger.success("初始化 genshin.py 相关资源成功")
        self._services.update({CallbackContext: context})
        logger.info("开始初始化服务")
        await self.start_services()
        logger.info("开始安装插件")
        await self.install_plugins()
        logger.info("BOT 初始化成功")

    def launch(self) -> NoReturn:
        """启动机器人"""
        self._running = True
        logger.info("正在初始化BOT")
        self.app = (
            TgApplication.builder()
            .read_timeout(self.config.read_timeout)
            .write_timeout(self.config.write_timeout)
            .connect_timeout(self.config.connect_timeout)
            .pool_timeout(self.config.pool_timeout)
            .get_updates_read_timeout(self.config.update_read_timeout)
            .get_updates_write_timeout(self.config.update_write_timeout)
            .get_updates_connect_timeout(self.config.update_connect_timeout)
            .get_updates_pool_timeout(self.config.update_pool_timeout)
            .rate_limiter(AIORateLimiter())
            .defaults(Defaults(tzinfo=pytz.timezone("Asia/Shanghai")))
            .token(self._config.bot_token)
            .post_init(self._post_init)
            .build()
        )
        try:
            for _ in range(5):
                try:
                    self.app.run_polling(
                        close_loop=False,
                        timeout=self.config.timeout,
                        allowed_updates=Update.ALL_TYPES,
                    )
                    break
                except TimedOut:
                    logger.warning("连接至 [blue]telegram[/] 服务器失败，正在重试", extra={"markup": True})
                    continue
                except NetworkError as e:
                    if "SSLZeroReturnError" in str(e):
                        logger.error("代理服务出现异常, 请检查您的代理服务是否配置成功.")
                    else:
                        logger.error("网络连接出现问题, 请检查您的网络状况.")
                    break
        except (SystemExit, KeyboardInterrupt):
            pass
        except Exception as e:  # pylint: disable=W0703
            logger.exception("BOT 执行过程中出现错误", exc_info=e)
        finally:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.stop_services())
            loop.close()
        logger.info("BOT 已经关闭")
        self._running = False

    def find_service(self, target: Type[T]) -> T:
        """查找服务。若没找到则抛出 ServiceNotFoundError"""
        if (result := self._services.get(target)) is None:
            raise ServiceNotFoundError(target)
        return result

    def add_service(self, service: T) -> NoReturn:
        """添加服务。若已经有同类型的服务，则会抛出异常"""
        if type(service) in self._services:
            raise ValueError(f'Service "{type(service)}" is already existed.')
        self.update_service(service)

    def update_service(self, service: T):
        """更新服务。若服务不存在，则添加；若存在，则更新"""
        self._services.update({type(service): service})

    def contain_service(self, service: Any) -> bool:
        """判断服务是否存在"""
        if isinstance(service, type):
            return service in self._services
        else:
            return service in self._services.values()

    @property
    def job_queue(self) -> JobQueue:
        return self.app.job_queue

    @property
    def services(self) -> Dict[Type[T], T]:
        return self._services

    @property
    def config(self) -> BotConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._running


bot = Bot()
