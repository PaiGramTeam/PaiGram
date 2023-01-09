"""插件"""
from dataclasses import asdict
from datetime import timedelta
from functools import wraps
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
from telegram.ext import BaseHandler, ConversationHandler, Job, TypeHandler

# noinspection PyProtectedMember
from typing_extensions import ParamSpec

from core.plugin._funcs import ConversationFuncs, PluginFuncs
from core.plugin._handler import ConversationDataType

if TYPE_CHECKING:
    from core.application import Application
    from core.plugin._handler import ConversationData, HandlerData
    from core.plugin._job import JobData
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["Plugin", "PluginType", "get_all_plugins"]

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")

HandlerType = TypeVar("HandlerType", bound=BaseHandler)

_HANDLER_DATA_ATTR_NAME = "_handler_datas"
"""用于储存生成 handler 时所需要的参数（例如 block）的属性名"""

_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_handler_data"
"""用于储存生成 ConversationHandler 时所需要的参数（例如 block）的属性名"""

_ERROR_HANDLER_ATTR_NAME = "_error_handler_data"

_JOB_ATTR_NAME = "_job_data"

_EXCLUDE_ATTRS = ["handlers", "jobs", "error_handlers"]


class _Plugin(PluginFuncs):
    """插件"""

    _lock: ClassVar["LockType"] = Lock()
    _installed: bool = False

    _handlers: Optional[List[HandlerType]] = None
    _error_handlers: Optional[List[Tuple[Callable, bool]]] = None
    _jobs: Optional[List[Job]] = None

    @property
    def handlers(self) -> List[HandlerType]:
        """该插件的所有 handler"""
        with self._lock:
            if self._handlers is None:
                self._handlers = []
                from core.builtins.executor import HandlerExecutor

                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and isinstance(func := getattr(self, attr), MethodType)
                        and (datas := getattr(func, _HANDLER_DATA_ATTR_NAME, []))
                    ):
                        for data in datas:
                            data: "HandlerData"
                            self._handlers.append(
                                data.type(
                                    callback=wraps(func)(HandlerExecutor(func, dispatcher=data.dispatcher)),
                                    **data.kwargs,
                                )
                            )
        return self._handlers

    @property
    def error_handlers(self) -> List[Tuple[Callable, bool]]:
        with self._lock:
            if self._error_handlers is None:
                self._error_handlers = []
                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and isinstance(func := getattr(self, attr), MethodType)
                        and (datas := getattr(func, _ERROR_HANDLER_ATTR_NAME, []))
                    ):
                        for data in datas:
                            self._error_handlers.append(data)
        return self._error_handlers

    def _install_jobs(self, app: "Application") -> None:
        from core.builtins.executor import JobExecutor

        if self._jobs is None:
            self._jobs = []
        for attr in dir(self):
            # noinspection PyUnboundLocalVariable
            if (
                not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                and isinstance(func := getattr(self, attr), MethodType)
                and (datas := getattr(func, _JOB_ATTR_NAME, []))
            ):
                for data in datas:
                    data: "JobData"
                    self._jobs.append(
                        getattr(app.tg_app.job_queue, data.type)(
                            callback=wraps(func)(JobExecutor(func, dispatcher=data.dispatcher)),
                            **data.kwargs,
                            **{
                                key: value
                                for key, value in asdict(data).items()
                                if key not in ["type", "kwargs", "dispatcher"]
                            },
                        )
                    )

    @property
    def jobs(self) -> List[Job]:
        return self._jobs

    async def __async_init__(self) -> None:
        """初始化插件"""

    async def __async_del__(self) -> None:
        """销毁插件"""

    async def install(self, app: "Application") -> None:
        """安装"""

        group = id(self)
        with self._lock:
            if not self._installed:
                self._install_jobs()
                for h in self.handlers:
                    if not isinstance(h, TypeHandler):
                        app.tg_app.add_handler(h, group)
                    else:
                        app.tg_app.add_handler(h, -1)
                for h in self.error_handlers:
                    app.tg_app.add_error_handler(*h)
                await self.__async_init__()
                self._installed = True

    async def uninstall(self, app: "Application") -> None:
        """卸载"""

        group = id(self)

        with self._lock:
            if self._installed:
                if group in app.tg_app.handlers:
                    del app.tg_app.handlers[id(self)]
                for h in self.handlers:
                    if isinstance(h, TypeHandler):
                        app.tg_app.remove_handler(h, -1)
                for h in self.error_handlers:
                    app.tg_app.remove_handler(h[0])
                for j in app.tg_app.job_queue.jobs():
                    j.schedule_removal()
                await self.__async_del__()
                self._installed = False

    async def reload(self, app: "Application") -> None:
        await self.uninstall(app)
        await self.install(app)


class _Conversation(_Plugin, ConversationFuncs):
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
                        conversation_data: "ConversationData"
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
    """获取所有 Plugin 的子类"""
    return filter(
        lambda x: x.__name__[0] != "_" and x not in [Plugin, _Plugin, _Conversation],
        chain(Plugin.__subclasses__(), _Conversation.__subclasses__()),
    )
