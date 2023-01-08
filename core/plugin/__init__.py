"""插件"""
from datetime import timedelta
from itertools import chain
from multiprocessing import RLock as Lock
from types import MethodType
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    List,
    Optional,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from pydantic import BaseModel

# noinspection PyProtectedMember
from telegram.ext import BaseHandler, ConversationHandler, TypeHandler

# noinspection PyProtectedMember
from typing_extensions import ParamSpec

from core.plugin._handler import ConversationData, ConversationDataType, conversation, handler
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

_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_handler_data"
"""用于储存生成 ConversationHandler 时所需要的参数（例如 block）的属性名"""

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

    async def __async_init__(self) -> None:
        """初始化插件"""

    async def __async_del__(self) -> None:
        """销毁插件"""

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
                await self.__async_init__()
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
                await self.__async_del__()
                self._initialized = False

    async def reload(self) -> None:
        await self.uninstall()
        await self.install()


class _Conversation(_Plugin):
    """Conversation类"""

    # noinspection SpellCheckingInspection
    class Config(BaseModel):
        allow_reetry: bool = False
        per_chat: bool = True
        per_user: bool = True
        per_message: bool = False
        conversation_timeout: Optional[Union[float, timedelta]] = None

    def __init_subclass__(cls, **kwargs):
        cls._conversation_kwargs = kwargs
        super(_Conversation, cls).__init_subclass__()
        return cls

    @property
    def handlers(self) -> List[HandlerType]:

        with self._lock:
            if not self._handlers:
                entry_points: List[HandlerType] = []
                states: Dict[Any, List[HandlerType]] = {}
                fallbacks: List[HandlerType] = []
                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and isinstance(func := getattr(self, attr), MethodType)
                        and (datas := getattr(func, _HANDLER_DATA_ATTR_NAME, []))
                    ):
                        conversation_data: ConversationData
                        handlers: List[HandlerType] = []
                        for data in datas:
                            handlers.append(data.handler)
                        if conversation_data := getattr(func, _CONVERSATION_HANDLER_ATTR_NAME, None):
                            if (_type := conversation_data.type) == ConversationDataType.Entry:
                                entry_points.extend(handlers)
                            elif _type == ConversationDataType.State:
                                if conversation_data.state in states:
                                    states[conversation_data.state].extend(handlers)
                                else:
                                    states[conversation_data.state] = handlers
                            elif _type == ConversationDataType.Fallback:
                                fallbacks.extend(handlers)
                        else:
                            self._handlers.extend(handlers)
                if entry_points and states and fallbacks:
                    self._handlers.append(ConversationHandler(entry_points, states, fallbacks, **self.Config().dict()))
        return self._handlers


class Plugin(_Plugin):
    """插件"""

    Conversation = _Conversation


PluginType = TypeVar("PluginType", bound=_Plugin)


def get_all_plugins() -> Iterable[Type[PluginType]]:
    return filter(
        lambda x: x.__name__[0] != "_" and x not in [Plugin],
        chain(Plugin.__subclasses__(), _Conversation.__subclasses__()),
    )
