"""参数分配器"""
from abc import ABC, abstractmethod
from functools import cached_property, partial, wraps
from multiprocessing import RLock as Lock
from types import MethodType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Sequence,
    TYPE_CHECKING,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

from arkowrapper import ArkoWrapper
from typing_extensions import ParamSpec, Self

from core.bot import Bot
from utils.const import WRAPPER_ASSIGNMENTS

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["catch", "AbstractDispatcher", "BaseDispatcher"]

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

TargetType = Union[Type, str, Callable[[Any], bool]]


# noinspection PyPep8Naming
class catch:
    _lock: "LockType" = Lock()

    _targets: List[TargetType]
    _catch_map: Dict[List[TargetType], Callable] = {}

    def __init__(self, *targets: Any) -> None:
        self._targets = list(targets)

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        with self._lock:
            self._catch_map.update({list(self._targets): func})
            self._targets = []

        setattr(func, "_catch_targets", self)
        return func

    def catch(self, target: TargetType) -> Self:
        if target not in self._targets:
            self._targets.append(target)
        return self

    def verify(self, instance: Any) -> Union[bool, Callable]:
        """用于验证是否为目标捕获类型"""
        for targets, func in self._catch_map.items():
            for target in targets:
                if target == instance:  # 直接相等
                    return func
                # 为 str
                if isinstance(instance, str) and isinstance(target, type) and target.__name__ == instance:
                    return func
        return False


def _catch(*targets: Union[str, Type]) -> Callable[[Callable[P, R]], Callable[P, R]]:
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

    def __init__(self, instances: Any) -> None:
        if not isinstance(instances, Sequence):
            instances = [instances]
        self._instances = instances

    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:

        params = {}

        for name, type_hint in get_type_hints(func):
            for catch_func in self.catch_funcs:
                catch_targets = getattr(catch_func, "_catch_targets")

                if name in catch_targets or type_hint in catch_targets:
                    params.update({name: catch_func()})

        return partial(func, **params)

    @catch(Bot)
    def catch_bot(self) -> "Bot":
        from core.bot import bot

        return bot


class DefaultDispatcher(BaseDispatcher):
    ...
