"""插件"""
from dataclasses import asdict
from datetime import timedelta
from functools import partial, wraps
from itertools import chain
from multiprocessing import RLock as Lock
from types import MethodType
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Optional,
    TYPE_CHECKING,
    Type,
    TypeVar,
    Union,
)

from pydantic import BaseModel

# noinspection PyProtectedMember
from telegram._utils.defaultvalue import DEFAULT_TRUE

# noinspection PyProtectedMember
from telegram._utils.types import DVInput

# noinspection PyProtectedMember
from telegram.ext import BaseHandler, ConversationHandler, Job, TypeHandler

# noinspection PyProtectedMember
from typing_extensions import ParamSpec

from core.builtins.contexts import ApplicationContext
from core.plugin._funcs import ConversationFuncs, PluginFuncs
from core.plugin._handler import ConversationDataType
from utils.const import WRAPPER_ASSIGNMENTS
from utils.log import logger

if TYPE_CHECKING:
    from core.application import Application
    from core.plugin._handler import ConversationData, HandlerData, ErrorHandlerData
    from core.plugin._job import JobData
    from multiprocessing.synchronize import RLock as LockType

__all__ = ("Plugin", "PluginType", "get_all_plugins")

wraps = partial(wraps, assigned=WRAPPER_ASSIGNMENTS)
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
    _error_handlers: Optional[List["ErrorHandlerData"]] = None
    _jobs: Optional[List[Job]] = None
    _application: "Optional[Application]" = None

    def set_application(self, application: "Application") -> None:
        self._application = application

    @property
    def application(self) -> "Application":
        if self._application is None:
            raise RuntimeError("No application was set for this Plugin.")
        return self._application

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
    def error_handlers(self) -> List["ErrorHandlerData"]:
        with self._lock:
            if self._error_handlers is None:
                from core.builtins.executor import HandlerExecutor

                self._error_handlers = []
                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and isinstance(func := getattr(self, attr), MethodType)
                        and (datas := getattr(func, _ERROR_HANDLER_ATTR_NAME, []))
                    ):
                        for data in datas:
                            data: "ErrorHandlerData"

                            data.func = wraps(func)(HandlerExecutor(func, dispatcher=data.dispatcher))

                            self._error_handlers.append(data)
        return self._error_handlers

    def _install_jobs(self) -> None:
        from core.builtins.executor import JobExecutor

        bot = ApplicationContext.get()

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
                        getattr(bot.telegram.job_queue, data.type)(
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
        with self._lock:
            if self._jobs is None:
                self._jobs = []
                self._install_jobs()
        return self._jobs

    async def initialize(self) -> None:
        """初始化插件"""

    async def shutdown(self) -> None:
        """销毁插件"""

    async def install(self) -> None:
        """安装"""
        bot = ApplicationContext.get()
        group = id(self)
        with self._lock:
            if not self._installed:
                self._install_jobs()

                for h in self.handlers:
                    if not isinstance(h, TypeHandler):
                        bot.telegram.add_handler(h, group)
                    else:
                        bot.telegram.add_handler(h, -1)

                for h in self.error_handlers:
                    bot.telegram.add_error_handler(h.func, h.block)

                await self.initialize()
                self._installed = True

    async def uninstall(self) -> None:
        """卸载"""
        bot = ApplicationContext.get()
        group = id(self)

        with self._lock:
            if self._installed:
                if group in bot.telegram.handlers:
                    del bot.telegram.handlers[id(self)]

                for h in self.handlers:
                    if isinstance(h, TypeHandler):
                        bot.telegram.remove_handler(h, -1)
                for h in self.error_handlers:
                    bot.telegram.remove_error_handler(h.func)

                for j in bot.telegram.job_queue.jobs():
                    j.schedule_removal()
                await self.shutdown()
                self._installed = False

    async def reload(self) -> None:
        await self.uninstall()
        await self.install()


class _Conversation(_Plugin, ConversationFuncs):
    """Conversation类"""

    # noinspection SpellCheckingInspection
    class Config(BaseModel):
        allow_reentry: bool = False
        per_chat: bool = True
        per_user: bool = True
        per_message: bool = False
        conversation_timeout: Optional[Union[float, timedelta]] = None
        name: Optional[str] = None
        map_to_parent: Optional[Dict[object, object]] = None
        block: DVInput[bool] = DEFAULT_TRUE

    def __init_subclass__(cls, **kwargs):
        cls._conversation_kwargs = kwargs
        super(_Conversation, cls).__init_subclass__()
        return cls

    @property
    def handlers(self) -> List[HandlerType]:

        with self._lock:
            if self._handlers is None:
                from core.builtins.executor import HandlerExecutor

                self._handlers = []

                entry_points: List[HandlerType] = []
                states: Dict[Any, List[HandlerType]] = {}
                fallbacks: List[HandlerType] = []
                for attr in dir(self):
                    if (
                        not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                        and (func := getattr(self, attr, None)) is not None
                        and (datas := getattr(func, _HANDLER_DATA_ATTR_NAME, []))
                    ):
                        conversation_data: "ConversationData"

                        handlers: List[HandlerType] = []
                        for data in datas:
                            handlers.append(
                                data.type(
                                    callback=wraps(func)(HandlerExecutor(func, dispatcher=data.dispatcher)),
                                    **data.kwargs,
                                )
                            )

                        if conversation_data := getattr(func, _CONVERSATION_HANDLER_ATTR_NAME, None):
                            if (_type := conversation_data.type) is ConversationDataType.Entry:
                                entry_points.extend(handlers)
                            elif _type is ConversationDataType.State:
                                if conversation_data.state in states:
                                    states[conversation_data.state].extend(handlers)
                                else:
                                    states[conversation_data.state] = handlers
                            elif _type is ConversationDataType.Fallback:
                                fallbacks.extend(handlers)
                            else:
                                self._handlers.extend(handlers)
                        else:
                            self._handlers.extend(handlers)
                if entry_points and states and fallbacks:
                    kwargs = self._conversation_kwargs
                    kwargs.update(self.Config().dict())
                    self._handlers.append(ConversationHandler(entry_points, states, fallbacks, **kwargs))
                else:
                    temp_dict = {"entry_points": entry_points, "states": states, "fallbacks": fallbacks}
                    reason = map(lambda x: f"'{x[0]}'", filter(lambda x: not x[1], temp_dict.items()))
                    logger.warning(f"'{self.__class__.__name__}' 因缺少 {', '.join(reason)} 而生成无法生成 ConversationHandler")
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
