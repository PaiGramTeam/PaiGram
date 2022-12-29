"""插件"""
import datetime
import re
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
    Pattern,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    TypedDict,
    Union,
)

# noinspection PyProtectedMember
from telegram._utils.defaultvalue import DEFAULT_TRUE

# noinspection PyProtectedMember
from telegram._utils.types import DVInput, JSONDict
from telegram.ext import BaseHandler, TypeHandler

# noinspection PyProtectedMember
from telegram.ext._utils.types import JobCallback
from telegram.ext.filters import BaseFilter
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["Plugin", "PluginType", "handler"]

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

_ERROR_HANDLER_ATTR_NAME = "_error_handler_data"

_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_handler_data"
"""用于储存生成 ConversationHandler 时所需要的参数（例如 block）的属性名"""

_JOB_ATTR_NAME = "_job_data"

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


class HandlerData(TypedDict):
    type: Type
    func: Callable
    args: Dict[str, Any]


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


class _Handler:
    _type: Type[HandlerType]

    kwargs: Dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        """用于获取 python-telegram-bot 中对应的 handler class"""
        cls._type = getattr(_Module, f"{cls.__name__.strip('_')}Handler", None)

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        handler_datas = getattr(func, _HANDLER_DATA_ATTR_NAME, [])
        handler_datas.append(HandlerFunc(self._type, func, self.kwargs))
        setattr(func, _HANDLER_DATA_ATTR_NAME, handler_datas)

        return func


class _CallbackQuery(_Handler):
    def __init__(
        self,
        pattern: Union[str, Pattern, type, Callable[[object], Optional[bool]]] = None,
        block: DVInput[bool] = DEFAULT_TRUE,
    ):
        super(_CallbackQuery, self).__init__(pattern=pattern, block=block)


class _ChatJoinRequest(_Handler):
    def __init__(self, block: DVInput[bool] = DEFAULT_TRUE):
        super(_ChatJoinRequest, self).__init__(block=block)


class _ChatMember(_Handler):
    def __init__(self, chat_member_types: int = -1):
        super().__init__(chat_member_types=chat_member_types)


class _ChosenInlineResult(_Handler):
    def __init__(self, block: DVInput[bool] = DEFAULT_TRUE, pattern: Union[str, Pattern] = None):
        super().__init__(block=block, pattern=pattern)


class _Command(_Handler):
    def __init__(self, command: str, filters: "BaseFilter" = None, block: DVInput[bool] = DEFAULT_TRUE):
        super(_Command, self).__init__(command=command, filters=filters, block=block)


class _InlineQuery(_Handler):
    def __init__(
        self, pattern: Union[str, Pattern] = None, block: DVInput[bool] = DEFAULT_TRUE, chat_types: List[str] = None
    ):
        super(_InlineQuery, self).__init__(pattern=pattern, block=block, chat_types=chat_types)


class _Message(_Handler):
    def __init__(self, filters: BaseFilter, block: DVInput[bool] = DEFAULT_TRUE) -> None:
        super(_Message, self).__init__(filters=filters, block=block)


class _PollAnswer(_Handler):
    def __init__(self, block: DVInput[bool] = DEFAULT_TRUE):
        super(_PollAnswer, self).__init__(block=block)


class _Poll(_Handler):
    def __init__(self, block: DVInput[bool] = DEFAULT_TRUE):
        super(_Poll, self).__init__(block=block)


class _PreCheckoutQuery(_Handler):
    def __init__(self, block: DVInput[bool] = DEFAULT_TRUE):
        super(_PreCheckoutQuery, self).__init__(block=block)


class _Prefix(_Handler):
    def __init__(
        self,
        prefix: str,
        command: str,
        filters: BaseFilter = None,
        block: DVInput[bool] = DEFAULT_TRUE,
    ):
        super(_Prefix, self).__init__(prefix=prefix, command=command, filters=filters, block=block)


class _ShippingQuery(_Handler):
    def __init__(self, block: DVInput[bool] = DEFAULT_TRUE):
        super(_ShippingQuery, self).__init__(block=block)


class _StringCommand(_Handler):
    def __init__(self, command: str):
        super(_StringCommand, self).__init__(command=command)


class _StringRegex(_Handler):
    def __init__(self, pattern: Union[str, Pattern], block: DVInput[bool] = DEFAULT_TRUE):
        super(_StringRegex, self).__init__(pattern=pattern, block=block)


class _Type(_Handler):
    # noinspection PyShadowingBuiltins
    def __init__(
        self,
        type: Type,
        strict: bool = False,
        block: DVInput[bool] = DEFAULT_TRUE
        # pylint: disable=redefined-builtin
    ):
        super(_Type, self).__init__(type=type, strict=strict, block=block)


# noinspection PyPep8Naming
class handler(_Handler):
    callback_query = _CallbackQuery
    chat_join_request = _ChatJoinRequest
    chat_member = _ChatMember
    chosen_inline_result = _ChosenInlineResult
    command = _Command
    inline_query = _InlineQuery
    message = _Message
    poll_answer = _PollAnswer
    pool = _Poll
    pre_checkout_query = _PreCheckoutQuery
    prefix = _Prefix
    shipping_query = _ShippingQuery
    string_command = _StringCommand
    string_regex = _StringRegex
    type = _Type

    def __init__(self, handler_type: Union[Callable[P, HandlerType], Type[HandlerType]], **kwargs: P.kwargs) -> None:
        self._type = handler_type
        super().__init__(**kwargs)

    def __init_subclass__(cls, **kwargs) -> None:
        for attr in [
            "callback_query",
            "chat_join_request",
            "chat_member",
            "chosen_inline_result",
            "command",
            "inline_query",
            "message",
            "poll_answer",
            "pool",
            "pre_checkout_query",
            "prefix",
            "shipping_query",
            "string_command",
            "string_regex",
            "type",
        ]:
            delattr(cls, attr)


# noinspection PyPep8Naming
class error_handler:
    def __init__(self, func: Callable[P, T] = None, *, block: bool = DEFAULT_TRUE):
        self._func = func
        self._block = block

    def __call__(self, func: Callable[P, T] = None) -> Callable[P, T]:
        self._func = func or self._func

        handler_datas = getattr(func, _ERROR_HANDLER_ATTR_NAME, [])
        handler_datas.append((self._func or func, self._block))
        setattr(func, _ERROR_HANDLER_ATTR_NAME, handler_datas)

        return func


def _entry(func: Callable[P, T]) -> Callable[P, T]:
    setattr(func, _CONVERSATION_HANDLER_ATTR_NAME, {"type": "entry"})
    return func


class _State:
    def __init__(self, state: Any):
        self.state = state

    def __call__(self, func: Callable[P, T] = None) -> Callable[P, T]:
        setattr(func, _CONVERSATION_HANDLER_ATTR_NAME, {"type": "state", "state": self.state})
        return func


def _fallback(func: Callable[P, T]) -> Callable[P, T]:
    setattr(func, _CONVERSATION_HANDLER_ATTR_NAME, {"type": "fallback"})
    return func


# noinspection PyPep8Naming
class conversation(_Handler):
    entry_point = _entry
    state = _State
    fallback = _fallback


class _Job:
    kwargs: Dict = {}

    def __init__(
        self,
        name: str = None,
        data: object = None,
        chat_id: int = None,
        user_id: int = None,
        job_kwargs: JSONDict = None,
        **kwargs,
    ):
        self.name = name
        self.data = data
        self.chat_id = chat_id
        self.user_id = user_id
        self.job_kwargs = {} if job_kwargs is None else job_kwargs
        self.kwargs = kwargs

    def __call__(self, func: JobCallback) -> JobCallback:
        data = {
            "name": self.name,
            "data": self.data,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "job_kwargs": self.job_kwargs,
            "kwargs": self.kwargs,
            "type": re.sub(r"([A-Z])", lambda x: "_" + x.group().lower(), self.__class__.__name__).lstrip("_"),
        }
        if hasattr(func, _JOB_ATTR_NAME):
            job_datas = getattr(func, _JOB_ATTR_NAME)
            job_datas.append(data)
            setattr(func, _JOB_ATTR_NAME, job_datas)
        else:
            setattr(func, _JOB_ATTR_NAME, [data])
        return func


class _RunOnce(_Job):
    def __init__(
        self,
        when: TimeType,
        data: object = None,
        name: str = None,
        chat_id: int = None,
        user_id: int = None,
        job_kwargs: JSONDict = None,
    ):
        super().__init__(name, data, chat_id, user_id, job_kwargs, when=when)


class _RunRepeating(_Job):
    def __init__(
        self,
        interval: Union[float, datetime.timedelta],
        first: TimeType = None,
        last: TimeType = None,
        data: object = None,
        name: str = None,
        chat_id: int = None,
        user_id: int = None,
        job_kwargs: JSONDict = None,
    ):
        super().__init__(name, data, chat_id, user_id, job_kwargs, interval=interval, first=first, last=last)


class _RunMonthly(_Job):
    def __init__(
        self,
        when: datetime.time,
        day: int,
        data: object = None,
        name: str = None,
        chat_id: int = None,
        user_id: int = None,
        job_kwargs: JSONDict = None,
    ):
        super().__init__(name, data, chat_id, user_id, job_kwargs, when=when, day=day)


class _RunDaily(_Job):
    def __init__(
        self,
        time: datetime.time,
        days: Tuple[int, ...] = tuple(range(7)),
        data: object = None,
        name: str = None,
        chat_id: int = None,
        user_id: int = None,
        job_kwargs: JSONDict = None,
    ):
        super().__init__(name, data, chat_id, user_id, job_kwargs, time=time, days=days)


class _RunCustom(_Job):
    def __init__(
        self,
        data: object = None,
        name: str = None,
        chat_id: int = None,
        user_id: int = None,
        job_kwargs: JSONDict = None,
    ):
        super().__init__(name, data, chat_id, user_id, job_kwargs)


# noinspection PyPep8Naming
class job:
    run_once = _RunOnce
    run_repeating = _RunRepeating
    run_monthly = _RunMonthly
    run_daily = _RunDaily
    run_custom = _RunCustom
