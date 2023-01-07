"""插件"""
from itertools import chain
from multiprocessing import RLock as Lock
from types import MethodType
from typing import (
    Callable,
    ClassVar,
    Iterable,
    List,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
)

# noinspection PyProtectedMember
from telegram.ext import BaseHandler, TypeHandler

# noinspection PyProtectedMember
from typing_extensions import ParamSpec

from core.plugin._handler import conversation, handler
from core.plugin._job import TimeType, job

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["Plugin", "PluginType", "handler", "job", "TimeType", "conversation", "get_all_plugins"]

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")

HandlerType = TypeVar("HandlerType", bound=BaseHandler)

_HANDLER_DATA_ATTR_NAME = "_handler_datas"
"""用于储存生成 handler 时所需要的参数（例如 block）的属性名"""

_ERROR_HANDLER_ATTR_NAME = "_error_handler_data"

_EXCLUDE_ATTRS = ["handlers", "jobs", "error_handlers"]


class _Plugin:
    """插件"""

    _lock: ClassVar["LockType"] = Lock()
    _initialized: bool = False

    _handlers: List[HandlerType] = []
    _error_handlers: List[Tuple[Callable, bool]] = []

    @property
    def handlers(self) -> List[HandlerType]:
        """该插件的所有 handler"""
        with self._lock:
            if not self._handlers:
                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and isinstance(func := getattr(self, attr), MethodType)
                        and (datas := getattr(func, _HANDLER_DATA_ATTR_NAME, []))
                    ):
                        for data in datas:
                            self._handlers.append(data.handler)
        return self._handlers

    @property
    def error_handlers(self) -> List[Tuple[Callable, bool]]:
        with self._lock:
            if not self._error_handlers:
                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and isinstance(func := getattr(self, attr), MethodType)
                        and (datas := getattr(func, _ERROR_HANDLER_ATTR_NAME, []))
                    ):
                        for data in datas:
                            self._error_handlers.append(data)
        return self._error_handlers

    async def initialize(self) -> None:
        """初始化插件的方法"""

    async def destroy(self) -> None:
        """销毁插件的方法"""

    async def install(self) -> None:
        """安装"""
        from core.bot import bot

        group = id(self)
        with self._lock:
            if not self._initialized:
                for h in self.handlers:
                    if not isinstance(h, TypeHandler):
                        bot.tg_app.add_handler(h, group)
                    else:
                        bot.tg_app.add_handler(h, -1)
                for h in self.error_handlers:
                    bot.tg_app.add_error_handler(*h)
                await self.initialize()
                self._initialized = True

    async def uninstall(self) -> None:
        """卸载"""
        from core.bot import bot

        group = id(self)

        with self._lock:
            if self._initialized:
                if group in bot.tg_app.handlers:
                    del bot.tg_app.handlers[id(self)]
                for h in self.handlers:
                    if isinstance(h, TypeHandler):
                        bot.tg_app.remove_handler(h, -1)
                for h in self.error_handlers:
                    bot.tg_app.remove_handler(h[0])
                await self.destroy()
                self._initialized = False

    async def reload(self) -> None:
        await self.uninstall()
        await self.install()


class _Conversation(_Plugin):
    """Conversation类"""


class Plugin(_Plugin):
    """插件"""

    Conversation = _Conversation

    def __init_subclass__(cls, **kwargs) -> None:
        delattr(cls, "Conversation")


PluginType = TypeVar("PluginType", bound=_Plugin)


def get_all_plugins() -> Iterable[Type[PluginType]]:
    return filter(
        lambda x: x.__name__[0] != "_" and x not in [Plugin],
        chain(Plugin.__subclasses__(), _Conversation.__subclasses__()),
    )
