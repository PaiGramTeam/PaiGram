import copy
import datetime
import re
from importlib import import_module
from re import Pattern
from types import MethodType
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

# noinspection PyProtectedMember
from telegram._utils.defaultvalue import DEFAULT_TRUE

# noinspection PyProtectedMember
from telegram._utils.types import DVInput, JSONDict
from telegram.ext import BaseHandler, ConversationHandler, Job

# noinspection PyProtectedMember
from telegram.ext._utils.types import JobCallback
from telegram.ext.filters import BaseFilter
from typing_extensions import ParamSpec

__all__ = ["Plugin", "handler", "conversation", "job", "error_handler"]

P = ParamSpec("P")
T = TypeVar("T")
HandlerType = TypeVar("HandlerType", bound=BaseHandler)
TimeType = Union[float, datetime.timedelta, datetime.datetime, datetime.time]

_Module = import_module("telegram.ext")

_NORMAL_HANDLER_ATTR_NAME = "_handler_data"
_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_data"
_JOB_ATTR_NAME = "_job_data"

_EXCLUDE_ATTRS = ["handlers", "jobs", "error_handlers"]


class _Plugin:
    def _make_handler(self, datas: Union[List[Dict], Dict]) -> List[HandlerType]:
        result = []
        if isinstance(datas, list):
            for data in filter(lambda x: x, datas):
                func = getattr(self, data.pop("func"))
                result.append(data.pop("type")(callback=func, **data.pop("kwargs")))
        else:
            func = getattr(self, datas.pop("func"))
            result.append(datas.pop("type")(callback=func, **datas.pop("kwargs")))
        return result

    @property
    def handlers(self) -> List[HandlerType]:
        result = []
        for attr in dir(self):
            # noinspection PyUnboundLocalVariable
            if (
                not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                and isinstance(func := getattr(self, attr), MethodType)
                and (datas := getattr(func, _NORMAL_HANDLER_ATTR_NAME, None))
            ):
                for data in datas:
                    if data["type"] not in ["error", "new_chat_member"]:
                        result.extend(self._make_handler(data))
        return result

    def _new_chat_members_handler_funcs(self) -> List[Tuple[int, Callable]]:
        result = []
        for attr in dir(self):
            # noinspection PyUnboundLocalVariable
            if (
                not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                and isinstance(func := getattr(self, attr), MethodType)
                and (datas := getattr(func, _NORMAL_HANDLER_ATTR_NAME, None))
            ):
                for data in datas:
                    if data and data["type"] == "new_chat_member":
                        result.append((data["priority"], func))

        return result

    @property
    def error_handlers(self) -> Dict[Callable, bool]:
        result = {}
        for attr in dir(self):
            # noinspection PyUnboundLocalVariable
            if (
                not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                and isinstance(func := getattr(self, attr), MethodType)
                and (datas := getattr(func, _NORMAL_HANDLER_ATTR_NAME, None))
            ):
                for data in datas:
                    if data and data["type"] == "error":
                        result.update({func: data["block"]})
        return result

    @property
    def jobs(self) -> List[Job]:
        from core.bot import bot

        result = []
        for attr in dir(self):
            # noinspection PyUnboundLocalVariable
            if (
                not (attr.startswith("_") or attr in _EXCLUDE_ATTRS)
                and isinstance(func := getattr(self, attr), MethodType)
                and (datas := getattr(func, _JOB_ATTR_NAME, None))
            ):
                for data in datas:
                    _job = getattr(bot.job_queue, data.pop("type"))(
                        callback=func, **data.pop("kwargs"), **{key: data.pop(key) for key in list(data.keys())}
                    )
                    result.append(_job)
        return result


class _Conversation(_Plugin):
    _conversation_kwargs: Dict

    def __init_subclass__(cls, **kwargs):
        cls._conversation_kwargs = kwargs
        super(_Conversation, cls).__init_subclass__()
        return cls

    @property
    def handlers(self) -> List[HandlerType]:
        result: List[HandlerType] = []

        entry_points: List[HandlerType] = []
        states: Dict[Any, List[HandlerType]] = {}
        fallbacks: List[HandlerType] = []
        for attr in dir(self):
            # noinspection PyUnboundLocalVariable
            if (
                not (attr.startswith("_") or attr == "handlers")
                and isinstance(func := getattr(self, attr), Callable)
                and (handler_datas := getattr(func, _NORMAL_HANDLER_ATTR_NAME, None))
            ):
                conversation_data = getattr(func, _CONVERSATION_HANDLER_ATTR_NAME, None)
                if attr == "cancel":
                    handler_datas = copy.deepcopy(handler_datas)
                    conversation_data = copy.deepcopy(conversation_data)
                _handlers = self._make_handler(handler_datas)
                if conversation_data:
                    if (_type := conversation_data.pop("type")) == "entry":
                        entry_points.extend(_handlers)
                    elif _type == "state":
                        if (key := conversation_data.pop("state")) in states:
                            states[key].extend(_handlers)
                        else:
                            states[key] = _handlers
                    elif _type == "fallback":
                        fallbacks.extend(_handlers)
                else:
                    result.extend(_handlers)
        if entry_points or states or fallbacks:
            result.append(
                ConversationHandler(
                    entry_points, states, fallbacks, **self.__class__._conversation_kwargs  # pylint: disable=W0212
                )
            )
        return result


class Plugin(_Plugin):
    Conversation = _Conversation


class _Handler:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @property
    def _type(self) -> Type[BaseHandler]:
        return getattr(_Module, f"{self.__class__.__name__.strip('_')}Handler")

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        data = {"type": self._type, "func": func.__name__, "kwargs": self.kwargs}
        if hasattr(func, _NORMAL_HANDLER_ATTR_NAME):
            handler_datas = getattr(func, _NORMAL_HANDLER_ATTR_NAME)
            handler_datas.append(data)
            setattr(func, _NORMAL_HANDLER_ATTR_NAME, handler_datas)
        else:
            setattr(func, _NORMAL_HANDLER_ATTR_NAME, [data])
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
        super().__init__(pattern=pattern, block=block, chat_types=chat_types)


class _MessageNewChatMembers(_Handler):
    def __init__(self, func: Callable[P, T] = None, *, priority: int = 5):
        super().__init__()
        self.func = func
        self.priority = priority

    def __call__(self, func: Callable[P, T] = None) -> Callable[P, T]:
        self.func = self.func or func
        data = {"type": "new_chat_member", "priority": self.priority}
        if hasattr(func, _NORMAL_HANDLER_ATTR_NAME):
            handler_datas = getattr(func, _NORMAL_HANDLER_ATTR_NAME)
            handler_datas.append(data)
            setattr(func, _NORMAL_HANDLER_ATTR_NAME, handler_datas)
        else:
            setattr(func, _NORMAL_HANDLER_ATTR_NAME, [data])
        return func


class _Message(_Handler):
    def __init__(
        self,
        filters: "BaseFilter",
        block: DVInput[bool] = DEFAULT_TRUE,
    ):
        super(_Message, self).__init__(filters=filters, block=block)

    new_chat_members = _MessageNewChatMembers


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
        self, type: Type, strict: bool = False, block: DVInput[bool] = DEFAULT_TRUE  # pylint: disable=redefined-builtin
    ):
        super(_Type, self).__init__(type=type, strict=strict, block=block)


# noinspection PyPep8Naming
class handler(_Handler):
    def __init__(self, handler_type: Callable[P, HandlerType], **kwargs: P.kwargs):
        self._type_ = handler_type
        super(handler, self).__init__(**kwargs)

    @property
    def _type(self) -> Type[BaseHandler]:
        # noinspection PyTypeChecker
        return self._type_

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


# noinspection PyPep8Naming
class error_handler:
    def __init__(self, func: Callable[P, T] = None, *, block: bool = DEFAULT_TRUE):
        self._func = func
        self._block = block

    def __call__(self, func: Callable[P, T] = None) -> Callable[P, T]:
        self._func = func or self._func
        data = {"type": "error", "block": self._block}
        if hasattr(func, _NORMAL_HANDLER_ATTR_NAME):
            handler_datas = getattr(func, _NORMAL_HANDLER_ATTR_NAME)
            handler_datas.append(data)
            setattr(func, _NORMAL_HANDLER_ATTR_NAME, handler_datas)
        else:
            setattr(func, _NORMAL_HANDLER_ATTR_NAME, [data])
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
