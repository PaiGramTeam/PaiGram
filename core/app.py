from importlib import import_module
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import Any, Callable, ClassVar, List, NoReturn, Optional, Type

from telegram.ext import Application as TgApplication

from core.config import AppConfig
from core.plugin import Plugin
from utils.const import PLUGIN_DIR, PROJECT_ROOT
from utils.log import logger
from utils.typed import StrOrPath

__all__ = ['application']


class Application(object):
    _lock: ClassVar[Lock] = Lock()
    _instance: ClassVar[Optional["Application"]] = None

    def __new__(cls, *args, **kwargs) -> "Application":
        """实现单例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = object.__new__(cls)
        return cls._instance

    config: AppConfig = AppConfig()
    app: Optional[TgApplication] = None

    _plugin_init_funcs: List[Callable[[TgApplication], Any]] = []

    def _instantiate_plugin(self, plugin: Type[Plugin]) -> Plugin:
        """用于实例化Plugin的方法"""
        return plugin()

    def install_plugins(self, plugin_path: Optional[StrOrPath] = None):
        if plugin_path is None:
            plugin_path = PLUGIN_DIR
        else:
            plugin_path = Path(plugin_path).resolve()

        for path in plugin_path.iterdir():
            if not path.name.startswith('_'):
                if path.is_dir():
                    pkg = str(path.relative_to(PROJECT_ROOT))
                else:
                    pkg = str(path.relative_to(PROJECT_ROOT)).split('.')[0]
                try:
                    module = import_module(pkg.replace('\\', '.'))
                except Exception as e:
                    logger.exception(e)
                    continue
                for attr in dir(module):
                    if isinstance(cls := getattr(module, attr), type) and issubclass(cls, Plugin) and cls != Plugin:
                        instance: Plugin = self._instantiate_plugin(cls)
                        for data in instance.handler_datas():
                            func = getattr(instance, data.pop('func'))
                            self.app.add_handler(data.pop('type')(callback=func, **data))
                        if hasattr(instance, 'init'):
                            self._plugin_init_funcs.append(getattr(instance, 'init'))

    async def _post_init(self, app: TgApplication) -> NoReturn:
        for func in self._plugin_init_funcs:
            try:
                await func(app)
            except Exception as e:
                breakpoint()

    def launch(self) -> NoReturn:
        self.app = TgApplication.builder().token(self.config.bot_token).post_init(self._post_init).build()
        self.install_plugins()
        self.app.run_polling()


application = Application()
