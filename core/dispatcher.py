"""参数分配器"""
from abc import ABC, abstractmethod
from functools import cached_property, partial, wraps
from types import MethodType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Sequence,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

from arkowrapper import ArkoWrapper
from telegram import Update
from telegram.ext import CallbackContext
from typing_extensions import ParamSpec

from core.bot import Bot
from utils.const import WRAPPER_ASSIGNMENTS

__all__ = ["catch", "AbstractDispatcher", "BaseDispatcher", "HandlerDispatcher"]

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

TargetType = Union[Type, str, Callable[[Any], bool]]


def catch(*targets: Union[str, Type]) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        setattr(func, "_catch_targets", targets)

        @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        return wrapper

    return decorate


class AbstractDispatcher(ABC):
    IGNORED_ATTRS = []

    @cached_property
    def catch_funcs(self) -> List[MethodType]:
        # noinspection PyTypeChecker
        return list(
            ArkoWrapper(dir(self))
            .filter(lambda x: not x.startswith("_"))
            .filter(lambda x: x not in self.IGNORED_ATTRS + ["dispatch", "catch_funcs"])
            .map(lambda x: getattr(self, x))
            .filter(lambda x: isinstance(x, MethodType))
            .filter(lambda x: hasattr(x, "_catch_targets"))
        )

    @abstractmethod
    async def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:
        """将参数分配给函数，从而合成一个无需参数即可执行的函数"""


class BaseDispatcher(AbstractDispatcher):
    _instances: Sequence[Any]

    @property
    def instance_map(self) -> Dict[Union[str, Type[T]], T]:
        result = {type(k).__name__: k for k in self._instances}
        result.update({type(k): k for k in self._instances})
        return result

    def __init__(self, *instances: Any) -> None:
        self._instances = list(instances)

    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:

        params = {}

        for name, type_hint in get_type_hints(func):
            params.update(
                {
                    name: (
                        self.instance_map.get(type_hint, None)
                        or self.instance_map.get(name, None)
                        or self.instance_map.get(type_hint.__name__, None)
                    )
                }
            )
        params = {k: v for k, v in params if v is not None}
        for name, type_hint in get_type_hints(func):
            for catch_func in self.catch_funcs:
                catch_targets = getattr(catch_func, "_catch_targets")

                for catch_target in catch_targets:
                    if isinstance(catch_target, str):
                        if name == catch_target or (isinstance(type_hint, type) and type_hint.__name__ == catch_target):
                            params.update({name: catch_func()})
                    elif isinstance(catch_target, type):
                        if name == catch_target.__name__ or type_hint.__name__ == catch_target.__name__:
                            params.update({name: catch_func()})
        return partial(func, **params)

    @catch(Bot)
    def catch_bot(self) -> "Bot":
        from core.bot import bot

        return bot


class HandlerDispatcher(BaseDispatcher):
    def __init__(self, update: Update, context: CallbackContext, *instances: Any) -> None:
        super().__init__(update, context, *instances)
        self._update = update
        self._context = context

    @catch(Update)
    def catch_update(self) -> Update:
        return self._update

    @catch(CallbackContext)
    def catch_context(self) -> CallbackContext:
        return self._context
