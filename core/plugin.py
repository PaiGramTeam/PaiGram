import inspect
from typing import Callable, ClassVar, Dict, List, NoReturn, Optional, TYPE_CHECKING, TypeVar

# noinspection PyProtectedMember
from telegram._utils.defaultvalue import DEFAULT_TRUE
# noinspection PyProtectedMember
from telegram._utils.types import DVInput
from telegram.ext import BaseHandler, CommandHandler
# noinspection PyProtectedMember
from telegram.ext.filters import BaseFilter
from typing_extensions import ParamSpec, Self

if TYPE_CHECKING:
    from telegram.ext import Application

P = ParamSpec('P')
T = TypeVar('T')
HandlerType = TypeVar('HandlerType', bound=BaseHandler)


class Plugin(object):
    _instance: ClassVar[Optional[Self]] = None

    async def init(self, app: 'Application') -> NoReturn:
        """当app刚启动时，需要运行的方法"""

    @classmethod
    def handler_datas(cls) -> List[Dict]:
        result = []
        for key in dir(cls):
            # noinspection PyUnboundLocalVariable
            if (
                    not key.startswith('_')
                    and
                    isinstance(attr := getattr(cls, key), Callable)
                    and
                    (kwargs := getattr(attr, 'handler_kwargs', None))
            ):
                result.append(kwargs)
        return result


class _Command(object):
    def __init__(
            self,
            command: str,
            filters: BaseFilter = None,
            block: DVInput[bool] = DEFAULT_TRUE
    ):
        self.kwargs = {'type': CommandHandler, 'command': command, 'filters': filters, 'block': block}

    def __call__(self, func: Callable):
        self.kwargs.update({'func': func.__name__})
        setattr(func, 'handler_kwargs', self.kwargs)
        return func


# noinspection PyPep8Naming
class handler(object):
    def __init__(self, handler_type: Callable[P, HandlerType], *args: P.args, **kwargs: P.kwargs):
        self._handler_type = handler_type
        self._args = args
        self._kwargs = kwargs

    def __call__(self, func: Callable, *args, **kwargs) -> HandlerType:
        from telegram.ext import Updater, CallbackContext

        def callback(updater: Updater, context: CallbackContext):
            signature = inspect.signature(func)
            breakpoint()
            return func(self, updater, context)

        return self._handler_type(*self._args, callback=callback, **self._kwargs)

    command = _Command
