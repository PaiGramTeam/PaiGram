from importlib import import_module
from multiprocessing import RLock as Lock
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    TYPE_CHECKING,
    Type,
    TypeVar,
    TypedDict,
    Union,
)

# noinspection PyProtectedMember
from telegram._utils.defaultvalue import DEFAULT_TRUE

# noinspection PyProtectedMember
from telegram._utils.types import DVInput
from telegram.ext import BaseHandler

# noinspection PyProtectedMember
from telegram.ext.filters import BaseFilter
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["handler"]

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")

HandlerType = TypeVar("HandlerType", bound=BaseHandler)
HandlerCls = Type[HandlerType]

_Module = import_module("telegram.ext")

_HANDLER_DATA_ATTR_NAME = "_handler_datas"
"""用于储存生成 handler 时所需要的参数（例如 block）的属性名"""

_ERROR_HANDLER_ATTR_NAME = "_error_handler_data"

_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_handler_data"
"""用于储存生成 ConversationHandler 时所需要的参数（例如 block）的属性名"""


class HandlerData(TypedDict):
    type: Type
    func: Callable
    args: Dict[str, Any]


class HandlerFunc:
    """处理器函数"""

    _lock: "LockType" = Lock()
    _handler: Optional[HandlerType] = None

    def __init__(self, handler_type: HandlerCls, func: Callable[P, R], kwargs: Dict):
        from core.builtins.executor import HandlerExecutor

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
    def __init__(self, chat_member_types: int = -1, block: DVInput[bool] = DEFAULT_TRUE):
        super().__init__(chat_member_types=chat_member_types, block=block)


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
