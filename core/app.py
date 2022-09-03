import asyncio
import inspect
from importlib import import_module
from multiprocessing import RLock as Lock
from typing import ClassVar, List, NoReturn, Optional, Type

import pytz
from telegram.error import TimedOut
from telegram.ext import Application as TgApplication, Defaults, JobQueue

from core.config import AppConfig
# noinspection PyProtectedMember
from core.plugin import _Plugin as Plugin
from core.service import Service
from utils.const import PLUGIN_DIR, PROJECT_ROOT, SERVICE_DIR
from utils.log import logger

__all__ = ['application']


class Application(object):
    _lock: ClassVar[Lock] = Lock()
    _instance: ClassVar[Optional["Application"]] = None

    def __new__(cls, *args, **kwargs) -> "Application":
        """实现单例"""
        with cls._lock:  # 使线程、进程安全
            if cls._instance is None:
                cls._instance = object.__new__(cls)
        return cls._instance

    app: Optional[TgApplication] = None
    config: AppConfig = AppConfig()
    services: List[Service] = []

    def _init_plugin(self, plugin: Type[Plugin]) -> Plugin:
        """用于实例化Plugin的方法。用于给插件传入一些必要组件，如 MySQL、Redis等"""
        signature = inspect.signature(plugin.__init__)
        kwargs = {}
        for name, parameter in signature.parameters.items():
            if name != 'self' and parameter.annotation != inspect.Parameter.empty:
                if s := list(filter(lambda x: type(x) == parameter.annotation, self.services)):
                    kwargs.update({name: s[0]})
        # noinspection PyArgumentList
        return plugin(**kwargs)

    async def install_plugins(self):
        """安装插件"""
        for path in PLUGIN_DIR.iterdir():  # 遍历插件所在的目录
            if not path.name.startswith('_'):
                if path.is_dir():
                    pkg = str(path.relative_to(PROJECT_ROOT))
                else:
                    pkg = str(path.relative_to(PROJECT_ROOT)).split('.')[0]
                try:
                    module = import_module(pkg := pkg.replace('\\', '.'))  # 导入插件
                except Exception as e:
                    logger.error(f'在导入插件 "{pkg}" 的过程中遇到了错误：')
                    logger.error(f"{type(e).__name__}: {e}")
                    continue  # 如有错误则继续
                for attr in dir(module):
                    # 找到该插件
                    if isinstance(cls := getattr(module, attr), type) and issubclass(cls, Plugin) and cls != Plugin:
                        instance: Plugin = self._init_plugin(cls)  # 实列化插件
                        if hasattr(instance, 'init'):
                            await instance.init()
                        self.app.add_handlers(instance.handlers)  # 添加 handler
                        for job in instance.jobs:  # 添加任务
                            func = getattr(instance, job.pop('func'))
                            getattr(self.job_queue, job.pop('type'))(
                                callback=func,
                                **job.pop('kwargs'),
                                **{key: job.pop(key) for key in list(job.keys())}
                            )
                logger.success(f'插件 "{pkg}" 载入成功')

    async def start_services(self):
        for path in SERVICE_DIR.iterdir():
            if not path.name.startswith('_') and path.is_file():
                pkg = str(path.relative_to(PROJECT_ROOT)).split('.')[0].replace('\\', '.')
                try:
                    import_module(pkg)
                except Exception as e:
                    logger.error(f"服务 \"{pkg}\" 在启动的过程中遇到了错误")
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
        for service in self.services:
            try:
                await service.stop()
                logger.success(f'服务 "{service.__class__.__name__}" 关闭成功')
            except Exception as e:
                logger.error(f"服务 \"{service.__class__.__name__}\" 关闭失败")
                logger.error(f"{type(e).__name__}: {e}")

    async def _post_init(self, app: TgApplication) -> NoReturn:
        await self.start_services()
        await self.install_plugins()

    def launch(self) -> NoReturn:
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
            for _ in range(5):
                try:
                    self.app.run_polling(close_loop=False)
                    break
                except TimedOut:
                    logger.warning(f"连接至 telegram 服务器失败，正在重试")
                    continue
        except (SystemExit, KeyboardInterrupt):
            pass
        except Exception as e:
            logger.info("BOT执行过程中出现错误")
            logger.exception(e)
        finally:
            logger.info('正在关闭服务')
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.stop_services())
            loop.close()
        logger.info('BOT 已经关闭')

    @property
    def job_queue(self) -> JobQueue:
        return self.app.job_queue


application = Application()
