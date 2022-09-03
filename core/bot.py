import asyncio
import inspect
from importlib import import_module
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import ClassVar, Iterator, List, NoReturn, Optional, Type, TypeVar

import pytz
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application as TgApplication, Defaults, JobQueue

from core.config import BotConfig
# noinspection PyProtectedMember
from core.plugin import Plugin, _Plugin
from core.service import Service
from utils.const import PLUGIN_DIR, PROJECT_ROOT, SERVICE_DIR
from utils.log import logger

__all__ = ['bot']

PluginType = TypeVar('PluginType', bound=_Plugin)


class Bot(object):
    _lock: ClassVar[Lock] = Lock()
    _instance: ClassVar[Optional["Bot"]] = None

    def __new__(cls, *args, **kwargs) -> "Bot":
        """实现单例"""
        with cls._lock:  # 使线程、进程安全
            if cls._instance is None:
                cls._instance = object.__new__(cls)
        return cls._instance

    app: Optional[TgApplication] = None
    config: BotConfig = BotConfig()
    services: List[Service] = []

    def _init_plugin(self, plugin_cls: Type[_Plugin]) -> _Plugin:
        """用于实例化Plugin的方法。用于给插件传入一些必要组件，如 MySQL、Redis等"""
        signature = inspect.signature(plugin_cls.__init__)
        kwargs = {}
        for name, parameter in signature.parameters.items():
            if name != 'self' and parameter.annotation != inspect.Parameter.empty:
                if s := list(filter(lambda x: type(x) is parameter.annotation, self.services)):
                    kwargs.update({name: s[0]})
        # noinspection PyArgumentList
        return plugin_cls(**kwargs)

    def _gen_plugin_pkg(self, root: Path = None) -> Iterator[str]:
        """生成可以用于 import_module 导入的字符串"""
        if root is None:
            root = PLUGIN_DIR
        for path in root.iterdir():
            if not path.name.startswith('_'):
                if path.is_dir():
                    yield from self._gen_plugin_pkg(path)
                elif path.suffix == '.py':
                    yield str(path.relative_to(PROJECT_ROOT)).split('.py')[0].replace('\\', '.')

    async def install_plugins(self):
        """安装插件"""
        for pkg in self._gen_plugin_pkg():
            try:
                import_module(pkg)  # 导入插件
            except Exception as e:
                logger.exception(e)
                logger.error(f'在导入文件 "{pkg}" 的过程中遇到了错误')
                logger.error(f"{type(e).__name__}: {e}")
                continue  # 如有错误则继续
        for plugin_cls in {*Plugin.__subclasses__(), *Plugin.Conversation.__subclasses__()}:
            path = f"{plugin_cls.__module__}.{plugin_cls.__name__}"
            try:
                plugin: PluginType = self._init_plugin(plugin_cls)
                if hasattr(plugin, '__async_init__'):
                    await plugin.__async_init__()
                handlers = plugin.handlers
                self.app.add_handlers(handlers)
                logger.debug(f'插件 "{path}" 添加了 {len(handlers)} 个 handler ')
                logger.debug(f'插件 "{path}" 添加了 {len(plugin.jobs)} 个任务')
                logger.success(f'插件 "{path}" 载入成功')
            except Exception as e:
                logger.exception(e)
                logger.error(f"在安装插件 \"{path}\" 的过程中遇到了错误")
                logger.error(f"{type(e).__name__}: {e}")

    async def start_services(self):
        """启动服务"""
        for path in SERVICE_DIR.iterdir():
            if not path.name.startswith('_') and path.is_file():
                pkg = str(path.relative_to(PROJECT_ROOT)).split('.')[0].replace('\\', '.')
                try:
                    import_module(pkg)
                except Exception as e:
                    logger.error(f'在导入文件 "{pkg}" 的过程中遇到了错误')
                    logger.error(f"{type(e).__name__}: {e}")
                    continue
        for service_class in Service.__subclasses__():
            try:
                if hasattr(service_class, 'from_config'):
                    instance = service_class.from_config(self.config)
                else:
                    instance = service_class()
                await instance.start()
                logger.success(f'服务 "{service_class.__name__}" 初始化成功')
                self.services.append(instance)
            except Exception as e:
                logger.error(f'服务 "{service_class.__name__}" 初始化失败', e)
                continue

    async def stop_services(self):
        """关闭服务"""
        if self.services:
            logger.info('正在关闭服务')
            for service in self.services:
                try:
                    await service.stop()
                    logger.success(f'服务 "{service.__class__.__name__}" 关闭成功')
                except Exception as e:
                    logger.exception(e)
                    logger.error(f"服务 \"{service.__class__.__name__}\" 关闭失败")
                    logger.error(f"{type(e).__name__}: {e}")

    async def _post_init(self, app: TgApplication) -> NoReturn:
        await self.start_services()
        await self.install_plugins()

    def launch(self) -> NoReturn:
        """启动机器人"""
        logger.info('正在初始化BOT')
        self.app = (
            TgApplication.builder()
            .defaults(Defaults(tzinfo=pytz.timezone("Asia/Shanghai")))
            .token(self.config.bot_token)
            .post_init(self._post_init)
            .build()
        )
        logger.info('BOT 初始化成功')
        try:
            for num in range(5):
                try:
                    self.app.run_polling(close_loop=False)
                    break
                except TimedOut:
                    logger.warning("连接至 [blue]telegram[/] 服务器失败，正在重试")
                    continue
                except NetworkError as e:
                    if 'SSLZeroReturnError' in str(e):
                        logger.error("代理服务出现异常, 请检查您的代理服务是否配置成功.")
                    else:
                        logger.error("网络连接出现问题, 请检查您的网络状况.")
                    break
        except (SystemExit, KeyboardInterrupt):
            pass
        except Exception as e:
            logger.info("BOT 执行过程中出现错误")
            logger.exception(e)
        finally:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.stop_services())
            loop.close()
        logger.info("BOT 已经关闭")

    @property
    def job_queue(self) -> JobQueue:
        return self.app.job_queue


bot = Bot()
