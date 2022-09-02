from importlib import import_module
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import Any, Callable, ClassVar, List, NoReturn, Optional, Type

import pytz
from telegram.ext import Application as TgApplication, Defaults

from core.config import AppConfig
from core.plugin import _Plugin as Plugin
from utils.const import PLUGIN_DIR, PROJECT_ROOT
from utils.log import logger
from utils.typed import StrOrPath

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

    config: AppConfig = AppConfig()
    app: Optional[TgApplication] = None

    _plugin_init_funcs: List[Callable[[TgApplication], Any]] = []

    def _instantiate_plugin(self, plugin: Type[Plugin]) -> Plugin:
        """用于实例化Plugin的方法。用于给插件传入一些必要组件，如 MySQL、Redis等"""
        return plugin()

    def install_plugins(self, plugin_path: Optional[StrOrPath] = None):
        """安装插件"""
        if plugin_path is None:
            plugin_path = PLUGIN_DIR
        else:
            plugin_path = Path(plugin_path).resolve()

        for path in plugin_path.iterdir():  # 遍历插件所在的目录
            if not path.name.startswith('_'):
                if path.is_dir():
                    pkg = str(path.relative_to(PROJECT_ROOT))
                else:
                    pkg = str(path.relative_to(PROJECT_ROOT)).split('.')[0]
                try:
                    module = import_module(pkg := pkg.replace('\\', '.'))  # 导入插件
                except Exception as e:
                    logger.error(
                        f'在导入插件 "{pkg}" 的过程中遇到了错误：\n'
                        f"[bold red]{type(e).__name__}: {e}[/]", extra={"markup": True}
                    )
                    continue  # 如有错误则继续
                for attr in dir(module):
                    # 找到该插件
                    if isinstance(cls := getattr(module, attr), type) and issubclass(cls, Plugin) and cls != Plugin:
                        instance: Plugin = self._instantiate_plugin(cls)  # 实列化插件
                        self.app.add_handlers(instance.handlers)  # 注册它的 handler
                        if hasattr(instance, 'init'):  # 如果有 init 函数 则将这个函数添加至 post_init
                            self._plugin_init_funcs.append(getattr(instance, 'init'))

    async def _post_init(self, app: TgApplication) -> NoReturn:
        for func in self._plugin_init_funcs:
            try:
                await func(app)
            except Exception as e:
                logger.exception(e)

    def launch(self) -> NoReturn:
        self.app = (
            TgApplication.builder()
            .defaults(Defaults(tzinfo=pytz.timezone("Asia/Shanghai")))
            .token(self.config.bot_token)
            .post_init(self._post_init)
            .build()
        )
        self.install_plugins()
        self.app.run_polling()


application = Application()
