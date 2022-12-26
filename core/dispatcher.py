"""参数分配器"""
import inspect
from abc import ABC, abstractmethod
from functools import cached_property, wraps
from types import MethodType
from typing import Any, Callable, List, ParamSpec, Sequence, TypeVar, get_type_hints

from arkowrapper import ArkoWrapper

from core.bot import Bot
from utils.const import WRAPPER_ASSIGNMENTS

__all__ = ["catch", "AbstractDispatcher", "BaseDispatcher"]

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


def catch(*targets: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
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
    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:
        """将参数分配给函数，从而合成一个无需参数即可执行的函数"""


class BaseDispatcher(AbstractDispatcher):
    _instances: Sequence[Any]

    def __init__(self, instances: Any) -> None:
        if not isinstance(instances, Sequence):
            instances = [instances]
        self._instances = instances

    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)

        for name, parameter in signature.parameters:
            type_hint = type_hints[name]

    @catch(Bot)
    def catch_bot(self) -> "Bot":
        from core.bot import bot

        return bot


class DefaultDispatcher(BaseDispatcher):
    ...
