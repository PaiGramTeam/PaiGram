import asyncio
import inspect
from importlib import import_module
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import ClassVar, Dict, Iterator, NoReturn, Optional, Type, TypeVar

import pytz
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application as TgApplication, Defaults, JobQueue

from core.config import BotConfig
# noinspection PyProtectedMember
from core.plugin import Plugin, _Plugin
from core.service import Service
from utils.const import PLUGIN_DIR, PROJECT_ROOT
from utils.log import logger

__all__ = ['bot']

T = TypeVar('T')
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
    services: Dict[Type[Service], Service] = {}

    def _init_inject(self, target: Type[T]) -> T:
        """用于实例化Plugin的方法。用于给插件传入一些必要组件，如 MySQL、Redis等"""
        signature = inspect.signature(target.__init__)
        kwargs = {}
        for name, parameter in signature.parameters.items():
            if name != 'self' and parameter.annotation != inspect.Parameter.empty:
                if value := self.services.get(parameter.annotation, None):
                    kwargs.update({name: value})
        # noinspection PyArgumentList
        return target(**kwargs)

    def _gen_pkg(self, root: Path) -> Iterator[str]:
        """生成可以用于 import_module 导入的字符串"""
        for path in root.iterdir():
            if not path.name.startswith('_'):
                if path.is_dir():
                    yield from self._gen_pkg(path)
                elif path.suffix == '.py':
                    yield str(path.relative_to(PROJECT_ROOT)).split('.py')[0].replace('\\', '.')

    async def install_plugins(self):
        """安装插件"""
        for pkg in self._gen_pkg(PLUGIN_DIR):
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
                plugin: PluginType = self._init_inject(plugin_cls)
                if hasattr(plugin, '__async_init__'):
                    await plugin.__async_init__()
                handlers = plugin.handlers
                self.app.add_handlers(handlers)
                if handlers:
                    logger.debug(f'插件 "{path}" 添加了 {len(handlers)} 个 handler ')
                if jobs := plugin.jobs:
                    logger.debug(f'插件 "{path}" 添加了 {len(jobs)} 个任务')
                logger.success(f'插件 "{path}" 载入成功')
            except Exception as e:
                logger.exception(e)
                logger.error(f"在安装插件 \"{path}\" 的过程中遇到了错误")
                logger.error(f"{type(e).__name__}: {e}")

    async def _start_base_services(self):
        for pkg in self._gen_pkg(PROJECT_ROOT / 'core/base'):
            try:
                import_module(pkg)
            except Exception as e:
                logger.error(f'在导入文件 "{pkg}" 的过程中遇到了错误')
                logger.error(f"{type(e).__name__}: {e}")
                continue
        for base_service_cls in Service.__subclasses__():
            try:
                if hasattr(base_service_cls, 'from_config'):
                    instance = base_service_cls.from_config(self.config)
                else:
                    instance = self._init_inject(base_service_cls)
                await instance.start()
                logger.success(f'服务 "{base_service_cls.__name__}" 初始化成功')
                self.services.update({base_service_cls: instance})
            except Exception as e:
                logger.error(f'服务 "{base_service_cls.__name__}" 初始化失败', e)
                continue

    async def _start_other_services(self):
        for pkg in self._gen_pkg(PROJECT_ROOT / 'core'):
            if len(splits := pkg.split('.')) > 2 and splits[1] != 'base':
                try:
                    import_module(pkg)
                except Exception as e:
                    logger.error(f'在导入文件 "{pkg}" 的过程中遇到了错误')
                    logger.error(f"{type(e).__name__}: {e}")
                    continue
        for service_cls in Service.__subclasses__():
            if service_cls not in self.services.keys():
                try:
                    instance = self._init_inject(service_cls)
                    await instance.start()
                    logger.success(f'服务 "{service_cls.__name__}" 初始化成功')
                    self.services.update({service_cls: instance})
                except Exception as e:
                    logger.error(f'服务 "{service_cls.__name__}" 初始化失败', e)
                    breakpoint()
                    continue

    async def start_services(self):
        """启动服务"""
        await self._start_base_services()
        await self._start_other_services()

    async def stop_services(self):
        """关闭服务"""
        if self.services:
            logger.info('正在关闭服务')
            for _, service in self.services.items():
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
