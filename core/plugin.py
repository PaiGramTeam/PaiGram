from importlib import import_module
from re import Pattern
from types import MethodType
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

# noinspection PyProtectedMember
from telegram._utils.defaultvalue import DEFAULT_TRUE
# noinspection PyProtectedMember
from telegram._utils.types import DVInput
from telegram.ext import BaseHandler, ConversationHandler
from telegram.ext.filters import BaseFilter
from typing_extensions import ParamSpec

__all__ = [
    'Plugin', 'handler', 'conversation'
]

P = ParamSpec('P')
T = TypeVar('T')
HandlerType = TypeVar('HandlerType', bound=BaseHandler)
_Module = import_module('telegram.ext')

_NORMAL_HANDLER_ATTR_NAME = "_handler_data"
_CONVERSATION_HANDLER_ATTR_NAME = "_conversation_data"


class _Plugin(object):
    def _make_handler(self, data: Dict) -> HandlerType:
        func = getattr(self, data.pop('func'))
        return data.pop('type')(callback=func, **data.pop('kwargs'))

    @property
    def handlers(self) -> List[HandlerType]:
        result = []
        for attr in dir(self):
            # noinspection PyUnboundLocalVariable
            if (
                    not (attr.startswith('_') or attr == 'handlers')
                    and
                    isinstance(func := getattr(self, attr), MethodType)
                    and
                    (data := getattr(func, 'handler_data', None))
            ):
                result.append(self._make_handler(data))
        return result


class _Conversation(_Plugin):
    _con_kwargs: Dict

    def __init_subclass__(cls, **kwargs):
        cls._con_kwargs = kwargs
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
                    not (attr.startswith('_') or attr == 'handlers')
                    and
                    isinstance(func := getattr(self, attr), Callable)
                    and
                    (handler_data := getattr(func, _NORMAL_HANDLER_ATTR_NAME, None))
            ):
                _handler = self._make_handler(handler_data)
                if conversation_data := getattr(func, _CONVERSATION_HANDLER_ATTR_NAME, None):
                    if (_type := conversation_data.pop('type')) == 'entry':
                        entry_points.append(_handler)
                    elif _type == 'state':
                        if (key := conversation_data.pop('state')) in states.keys():
                            states[key].append(_handler)
                        else:
                            states[key] = [_handler]
                    elif _type == 'fallback':
                        fallbacks.append(_handler)
                    else:
                        raise TypeError(_type)
                else:
                    result.append(_handler)
        if entry_points and states and fallbacks:
            result.append(
                ConversationHandler(entry_points, states, fallbacks, **self.__class__._con_kwargs)
            )
        return result


class Plugin(_Plugin):
    Conversation = _Conversation


class _Handler(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @property
    def _type(self) -> Type[BaseHandler]:
        return getattr(_Module, f"{self.__class__.__name__.strip('_')}Handler")

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        setattr(func, _NORMAL_HANDLER_ATTR_NAME, {'type': self._type, 'func': func.__name__, 'kwargs': self.kwargs})
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
            self,
            pattern: Union[str, Pattern] = None,
            block: DVInput[bool] = DEFAULT_TRUE,
            chat_types: List[str] = None
    ):
        super().__init__(pattern=pattern, block=block, chat_types=chat_types)


class _Message(_Handler):
    def __init__(self, filters: "BaseFilter", block: DVInput[bool] = DEFAULT_TRUE, ):
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
            type: Type,  # pylint: disable=redefined-builtin
            strict: bool = False,
            block: DVInput[bool] = DEFAULT_TRUE
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


def _entry(func: Callable[P, T]) -> Callable[P, T]:
    setattr(func, _CONVERSATION_HANDLER_ATTR_NAME, {'type': 'entry'})
    return func


class _State(object):
    def __init__(self, state: Any):
        self._state = state

    def __call__(self, func: Callable[P, T] = None) -> Callable[P, T]:
        setattr(func, _CONVERSATION_HANDLER_ATTR_NAME, {'type': 'state', 'state': self._state})
        return func


def _fallback(func: Callable[P, T]) -> Callable[P, T]:
    setattr(func, _CONVERSATION_HANDLER_ATTR_NAME, {'type': 'fallback'})
    return func


# noinspection PyPep8Naming
class conversation(_Handler):
    entry_point = _entry
    state = _State
    fallback = _fallback
