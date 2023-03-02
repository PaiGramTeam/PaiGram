from dataclasses import dataclass
from enum import Enum
from functools import wraps
from importlib import import_module
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Pattern,
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
from telegram.ext import BaseHandler
from telegram.ext.filters import BaseFilter
from typing_extensions import ParamSpec

from core.handler.callbackqueryhandler import CallbackQueryHandler
from utils.const import WRAPPER_ASSIGNMENTS as _WRAPPER_ASSIGNMENTS

if TYPE_CHECKING:
    from core.builtins.dispatcher import AbstractDispatcher

__all__ = (
    "handler",
    "conversation",
    "ConversationDataType",
    "ConversationData",
    "HandlerData",
    "ErrorHandlerData",
    "error_handler",
)

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")
UT = TypeVar("UT")

HandlerType = TypeVar("HandlerType", bound=BaseHandler)
HandlerCls = Type[HandlerType]

Module = import_module("telegram.ext")

HANDLER_DATA_ATTR_NAME = "_handler_datas"
"""用于储存生成 handler 时所需要的参数（例如 block）的属性名"""

ERROR_HANDLER_ATTR_NAME = "_error_handler_data"

CONVERSATION_HANDLER_ATTR_NAME = "_conversation_handler_data"
"""用于储存生成 ConversationHandler 时所需要的参数（例如 block）的属性名"""

WRAPPER_ASSIGNMENTS = list(
    set(
        _WRAPPER_ASSIGNMENTS
        + [
            HANDLER_DATA_ATTR_NAME,
            ERROR_HANDLER_ATTR_NAME,
            CONVERSATION_HANDLER_ATTR_NAME,
        ]
    )
)


@dataclass(init=True)
class HandlerData:
    type: Type[HandlerType]
    admin: bool
    kwargs: Dict[str, Any]
    dispatcher: Optional[Type["AbstractDispatcher"]] = None


class _Handler:
    _type: Type["HandlerType"]

    kwargs: Dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        """用于获取 python-telegram-bot 中对应的 handler class"""

        handler_name = f"{cls.__name__.strip('_')}Handler"

        if handler_name == "CallbackQueryHandler":
            cls._type = CallbackQueryHandler
            return

        cls._type = getattr(Module, handler_name, None)

    def __init__(self, admin: bool = False, dispatcher: Optional[Type["AbstractDispatcher"]] = None, **kwargs) -> None:
        self.dispatcher = dispatcher
        self.admin = admin
        self.kwargs = kwargs

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        """decorator实现，从 func 生成 Handler"""

        handler_datas = getattr(func, HANDLER_DATA_ATTR_NAME, [])
        handler_datas.append(
            HandlerData(type=self._type, admin=self.admin, kwargs=self.kwargs, dispatcher=self.dispatcher)
        )
        setattr(func, HANDLER_DATA_ATTR_NAME, handler_datas)

        return func


class _CallbackQuery(_Handler):
    def __init__(
        self,
        pattern: Union[str, Pattern, type, Callable[[object], Optional[bool]]] = None,
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        admin: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super(_CallbackQuery, self).__init__(pattern=pattern, block=block, admin=admin, dispatcher=dispatcher)


class _ChatJoinRequest(_Handler):
    def __init__(self, *, block: DVInput[bool] = DEFAULT_TRUE, dispatcher: Optional[Type["AbstractDispatcher"]] = None):
        super(_ChatJoinRequest, self).__init__(block=block, dispatcher=dispatcher)


class _ChatMember(_Handler):
    def __init__(
        self,
        chat_member_types: int = -1,
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super().__init__(chat_member_types=chat_member_types, block=block, dispatcher=dispatcher)


class _ChosenInlineResult(_Handler):
    def __init__(
        self,
        block: DVInput[bool] = DEFAULT_TRUE,
        *,
        pattern: Union[str, Pattern] = None,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super().__init__(block=block, pattern=pattern, dispatcher=dispatcher)


class _Command(_Handler):
    def __init__(
        self,
        command: Union[str, List[str]],
        filters: "BaseFilter" = None,
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        admin: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super(_Command, self).__init__(
            command=command, filters=filters, block=block, admin=admin, dispatcher=dispatcher
        )


class _InlineQuery(_Handler):
    def __init__(
        self,
        pattern: Union[str, Pattern] = None,
        chat_types: List[str] = None,
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super(_InlineQuery, self).__init__(pattern=pattern, block=block, chat_types=chat_types, dispatcher=dispatcher)


class _Message(_Handler):
    def __init__(
        self,
        filters: BaseFilter,
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        admin: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ) -> None:
        super(_Message, self).__init__(filters=filters, block=block, admin=admin, dispatcher=dispatcher)


class _PollAnswer(_Handler):
    def __init__(self, *, block: DVInput[bool] = DEFAULT_TRUE, dispatcher: Optional[Type["AbstractDispatcher"]] = None):
        super(_PollAnswer, self).__init__(block=block, dispatcher=dispatcher)


class _Poll(_Handler):
    def __init__(self, *, block: DVInput[bool] = DEFAULT_TRUE, dispatcher: Optional[Type["AbstractDispatcher"]] = None):
        super(_Poll, self).__init__(block=block, dispatcher=dispatcher)


class _PreCheckoutQuery(_Handler):
    def __init__(self, *, block: DVInput[bool] = DEFAULT_TRUE, dispatcher: Optional[Type["AbstractDispatcher"]] = None):
        super(_PreCheckoutQuery, self).__init__(block=block, dispatcher=dispatcher)


class _Prefix(_Handler):
    def __init__(
        self,
        prefix: str,
        command: str,
        filters: BaseFilter = None,
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super(_Prefix, self).__init__(
            prefix=prefix, command=command, filters=filters, block=block, dispatcher=dispatcher
        )


class _ShippingQuery(_Handler):
    def __init__(self, *, block: DVInput[bool] = DEFAULT_TRUE, dispatcher: Optional[Type["AbstractDispatcher"]] = None):
        super(_ShippingQuery, self).__init__(block=block, dispatcher=dispatcher)


class _StringCommand(_Handler):
    def __init__(
        self,
        command: str,
        *,
        admin: bool = False,
        block: DVInput[bool] = DEFAULT_TRUE,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super(_StringCommand, self).__init__(command=command, block=block, admin=admin, dispatcher=dispatcher)


class _StringRegex(_Handler):
    def __init__(
        self,
        pattern: Union[str, Pattern],
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        admin: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):
        super(_StringRegex, self).__init__(pattern=pattern, block=block, admin=admin, dispatcher=dispatcher)


class _Type(_Handler):
    # noinspection PyShadowingBuiltins
    def __init__(
        self,
        type: Type[UT],  # pylint: disable=W0622
        strict: bool = False,
        *,
        block: DVInput[bool] = DEFAULT_TRUE,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
    ):  # pylint: disable=redefined-builtin
        super(_Type, self).__init__(type=type, strict=strict, block=block, dispatcher=dispatcher)


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

    def __init__(
        self,
        handler_type: Union[Callable[P, "HandlerType"], Type["HandlerType"]],
        *,
        admin: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
        **kwargs: P.kwargs,
    ) -> None:
        self._type = handler_type
        super().__init__(admin=admin, dispatcher=dispatcher, **kwargs)


class ConversationDataType(Enum):
    """conversation handler 的类型"""

    Entry = "entry"
    State = "state"
    Fallback = "fallback"


class ConversationData(BaseModel):
    """用于储存 conversation handler 的数据"""

    type: ConversationDataType
    state: Optional[Any] = None


class _ConversationType:
    _type: ClassVar[ConversationDataType]

    def __init_subclass__(cls, **kwargs) -> None:
        cls._type = ConversationDataType(cls.__name__.lstrip("_").lower())


def _entry(func: Callable[P, R]) -> Callable[P, R]:
    setattr(func, CONVERSATION_HANDLER_ATTR_NAME, ConversationData(type=ConversationDataType.Entry))

    @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        return func(*args, **kwargs)

    return wrapped


class _State(_ConversationType):
    def __init__(self, state: Any) -> None:
        self.state = state

    def __call__(self, func: Callable[P, T] = None) -> Callable[P, T]:
        setattr(func, CONVERSATION_HANDLER_ATTR_NAME, ConversationData(type=self._type, state=self.state))
        return func


def _fallback(func: Callable[P, R]) -> Callable[P, R]:
    setattr(func, CONVERSATION_HANDLER_ATTR_NAME, ConversationData(type=ConversationDataType.Fallback))

    @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        return func(*args, **kwargs)

    return wrapped


# noinspection PyPep8Naming
class conversation(_Handler):
    entry_point = _entry
    state = _State
    fallback = _fallback


@dataclass(init=True)
class ErrorHandlerData:
    block: bool
    func: Optional[Callable] = None


# noinspection PyPep8Naming
class error_handler:
    _func: Callable[P, R]

    def __init__(
        self,
        *,
        block: bool = DEFAULT_TRUE,
    ):
        self._block = block

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        self._func = func
        wraps(func, assigned=WRAPPER_ASSIGNMENTS)(self)

        handler_datas = getattr(func, ERROR_HANDLER_ATTR_NAME, [])
        handler_datas.append(ErrorHandlerData(block=self._block))
        setattr(self._func, ERROR_HANDLER_ATTR_NAME, handler_datas)

        return self._func
