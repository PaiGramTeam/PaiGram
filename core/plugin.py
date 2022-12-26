"""插件"""
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

__all__ = ["Plugin", "handler"]

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")

HandlerType = TypeVar("HandlerType", bound=BaseHandler)
HandlerCls = Type[HandlerType]
TimeType = Union[float, datetime.timedelta, datetime.datetime, datetime.time]

_Module = import_module("telegram.ext")

_HANDLER_ATTR_NAME = "_handler"

_HANDLER_DATA_ATTR_NAME = "_handler_datas"
"""用于储存生成 handler 时所需要的参数（例如 block）的属性名"""

_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_data"
"""用于储存生成 ConversationHandler 时所需要的参数（例如 block）的属性名"""

_JOB_ATTR_NAME = "_job_data"

_EXCLUDE_ATTRS = ["handlers", "jobs", "error_handlers"]


class _Plugin:
    """插件"""

    _lock: ClassVar["LockType"] = Lock()
    _initialized: bool = False

    _handlers: List[HandlerType] = []

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

    async def initialize(self) -> None:
        """初始化插件的方法"""

    async def destroy(self) -> None:
        """销毁插件的方法"""

    async def install(self) -> None:
        from core.bot import bot

        with self._lock:
            if not self._initialized:
                bot.tg_app.add_handlers(self.handlers, group=id(self))
                await self.initialize()
                self._initialized = True

    async def uninstall(self) -> None:
        from core.bot import bot

        with self._lock:
            if self._initialized:
                if id(self) in bot.tg_app.handlers:
                    del bot.tg_app.handlers[id(self)]
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


class HandlerData(TypedDict):
    type: Type
    func: Callable
    args: Dict[str, Any]


class _HandlerMeta:
    """handler 元类。用于获取 python-telegram-bot 中对应的 handler class"""

    def __init_subclass__(cls, **kwargs) -> None:
        cls.type = getattr(_Module, f"{cls.__name__.strip('_')}Handler")


class HandlerFunc:
    """处理器函数"""

    _lock: "LockType" = Lock()
    _handler: Optional[HandlerType] = None

    def __init__(self, handler_type: HandlerCls, func: Callable[P, R], kwargs: Dict):
        from core.executor import HandlerExecutor

        self.type = handler_type
        self.callback = HandlerExecutor(func)
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
