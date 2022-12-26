"""执行器"""
import inspect
from multiprocessing import RLock as Lock
from typing import Any, Callable, ClassVar, Dict, Generic, TYPE_CHECKING, TypeVar

from telegram.ext import CallbackContext

# noinspection PyProtectedMember
from telegram.ext._utils.types import HandlerCallback
from typing_extensions import ParamSpec, Self

from core.dispatcher import AbstractDispatcher, BaseDispatcher
from utils.decorator import do_nothing
from utils.models.lock import HashLock

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["Executor", "HandlerExecutor"]

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


class Executor:
    """执行器

    只支持执行只拥有 POSITIONAL_OR_KEYWORD 和 KEYWORD_ONLY 两种参数类型的函数
    """

    _lock: ClassVar["LockType"] = Lock()
    _instances: ClassVar[Dict[str, Self]] = {}

    def __new__(cls, name: str):
        with cls._lock:
            if (instance := cls._instances.get(name, None)) is None:
                instance = object.__new__(cls)
                instance.__init__(name)
                cls._instances.update({name: instance})
        return instance

    @property
    def name(self) -> str:
        return self._name

    def __init__(self, name: str) -> None:
        self._name = name

    async def __call__(
        self,
        target: Callable[P, R],
        *instances: Any,
        block: bool = False,
        dispatcher: AbstractDispatcher = BaseDispatcher,
        lock_id: int = None,
    ) -> R:

        with (HashLock(lock_id or target) if block else do_nothing()):
            dispatched_func = BaseDispatcher(instances).dispatch(target)

            if inspect.iscoroutinefunction(target):
                result = await dispatched_func()
            else:
                result = dispatched_func()

        return result


class HandlerExecutor(Generic[P, R]):
    callback: Callable[P, R]
    executor: Executor = Executor("handler")

    def __init__(self, func: Callable[P, R]) -> None:
        self.callback = func

    async def __call__(self, callback: HandlerCallback, context: CallbackContext) -> R:
        return await self.executor(self.callback, callback, context)
