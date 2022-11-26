import datetime
from importlib import import_module
from multiprocessing import RLock as Lock
from types import MethodType
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    Type,
    TypeVar,
    TypedDict,
    Union,
)

from telegram.ext import BaseHandler
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")

HandlerType = TypeVar("HandlerType", bound=BaseHandler)
HandlerCls = Type[HandlerType]
TimeType = Union[float, datetime.timedelta, datetime.datetime, datetime.time]

_Module = import_module("telegram.ext")

_HANDLER_ATTR_NAME = "_handler"
_HANDLER_DATA_ATTR_NAME = "_handler_datas"
_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_data"
_JOB_ATTR_NAME = "_job_data"

_EXCLUDE_ATTRS = ["handlers", "jobs", "error_handlers"]


# noinspection PyProtectedMember
class PluginController:
    """插件的控制器"""

    _plugin: "_Plugin"

    @property
    def plugin(self) -> "_Plugin":
        return self._plugin

    def __init__(self, plugin: "_Plugin") -> None:
        self._plugin = plugin

    async def install(self) -> None:
        """安装此插件"""
        from core.bot import bot

        await self.plugin._initialize()
        bot.tg_app.add_handlers(self.plugin.handlers)

    async def uninstall(self) -> None:
        """卸载此插件"""
        from core.bot import bot

        bot.tg_app.remove_handlers(self.plugin.handlers)
        await self.plugin._destroy()

    async def reinstall(self) -> None:
        """重载此插件"""
        await self.uninstall()
        await self.install()


class _Plugin:
    """插件"""

    _lock: ClassVar[LockType] = Lock()
    _initialized: bool = False

    _handlers: List[HandlerType] = []

    @property
    def controller(self) -> "PluginController":
        return self._controller

    def __init__(self) -> None:
        self._controller = PluginController(self)

    @property
    def handlers(self) -> List[HandlerType]:
        """该插件的所有 handler"""
        with self._lock:
            if not self._handlers:
                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and isinstance(func := getattr(self, attr), MethodType)
                        and (datas := getattr(func, _HANDLER_DATA_ATTR_NAME, None))
                    ):
                        for data in datas:
                            self._handlers.append(data.handler)
        return self._handlers

    async def initialize(self) -> None:
        """初始化此插件"""

    async def destroy(self) -> None:
        """销毁此插件"""

    async def _initialize(self) -> None:
        with self._lock:
            if not self._initialized:
                await self.initialize()
                self._initialized = True

    async def _destroy(self) -> None:
        with self._lock:
            if self._initialized:
                await self.destroy()
                self._initialized = False


class _Conversation(_Plugin):
    """Conversation类"""


class Plugin(_Plugin):
    """插件"""

    Conversation = _Conversation


class HandlerData(TypedDict):
    type: Type
    func: Callable
    args: Dict[str, Any]


class _HandlerMeta:
    def __init_subclass__(cls, **kwargs):
        cls.type = getattr(_Module, f"{cls.__name__.strip('_')}Handler")


class HandlerFunc:
    _lock: "LockType" = Lock()
    _handler: Optional[HandlerType] = None

    def __init__(self, handler_type: HandlerCls, func: Callable[P, R], kwargs: Dict):
        self.type = handler_type
        self.callback = func
        self.kwargs = kwargs

    @property
    def handler(self) -> HandlerType:
        with self._lock:
            if self._handler is None:
                self._handler = self._handler or self.type(**self.kwargs, callback=self.callback)
        return self._handler


class _Handler(_HandlerMeta):
    type: Type[HandlerType]

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        handler_datas = getattr(func, _HANDLER_DATA_ATTR_NAME, [])
        handler_datas.append(HandlerFunc(self.type, func, self.kwargs))
        setattr(func, _HANDLER_DATA_ATTR_NAME, handler_datas)
        return func


# noinspection PyPep8Naming
class handler(_Handler):
    def __init__(self, handler_type: Union[Callable[P, HandlerType], Type[HandlerType]], **kwargs: P.kwargs) -> None:
        self.type = handler_type
        super(handler, self).__init__(**kwargs)
