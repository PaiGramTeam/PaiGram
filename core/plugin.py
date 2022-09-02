from importlib import import_module
from re import Pattern
from typing import Callable, Dict, List, Optional, Type, TypeVar, Union

# noinspection PyProtectedMember
from telegram._utils.defaultvalue import DEFAULT_TRUE
# noinspection PyProtectedMember
from telegram._utils.types import DVInput
from telegram.ext import BaseHandler
from telegram.ext.filters import BaseFilter
from typing_extensions import ParamSpec

__all__ = [
    'Plugin', 'handler', 'conversation'
]

P = ParamSpec('P')
T = TypeVar('T')
HandlerType = TypeVar('HandlerType', bound=BaseHandler)
Module = import_module('telegram.ext')


class _Plugin(object):
    _handlers: List[HandlerType] = None

    def _make_handler(self, data: Dict) -> HandlerType:
        func = getattr(self, data.pop('func'))
        return data.pop('type')(callback=func, **data.pop('kwargs'))

    @property
    def handlers(self) -> List[HandlerType]:
        if self._handlers is None:
            self._handlers = []
            for attr in dir(self):
                if (
                        not attr.startswith('_')
                        and
                        isinstance(attr := getattr(self, attr), Callable)
                        and
                        (data := getattr(attr, 'handler_data', None))
                ):
                    self._handlers.append(self._make_handler(data))
        return self._handlers


class _Conversation(_Plugin):
    ...


class Plugin(_Plugin):
    Conversation = _Conversation


class _Handler(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @property
    def type(self) -> Type[BaseHandler]:
        return getattr(Module, f"{self.__class__.__name__.strip('_')}Handler")

    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        setattr(func, 'handler_data', {'type': self.type, 'func': func.__name__, 'kwargs': self.kwargs})
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
    def __init__(self, command: str, filters: BaseFilter = None, block: DVInput[bool] = DEFAULT_TRUE):
        super(_Command, self).__init__(command=command, filters=filters, block=block)


# noinspection PyPep8Naming
class handler(_Handler):
    def __init__(self, handler_type: Callable[P, HandlerType], **kwargs: P.kwargs):
        self._type = handler_type
        super(handler, self).__init__(**kwargs)

    @property
    def type(self) -> Type[BaseHandler]:
        # noinspection PyTypeChecker
        return self._type

    callback_query = _CallbackQuery
    chat_join_request = _ChatJoinRequest
    command = _Command


class conversation(_Handler):
    pass
