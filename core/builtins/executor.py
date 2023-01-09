"""执行器"""
import inspect
from functools import cached_property
from multiprocessing import RLock as Lock
from typing import Callable, ClassVar, Dict, Generic, Optional, TYPE_CHECKING, Type, TypeVar

from telegram import Update
from telegram.ext import CallbackContext
from typing_extensions import ParamSpec, Self

from core.builtins.contexts import handler_contexts, job_contexts
from utils.decorator import do_nothing
from utils.models.lock import HashLock

if TYPE_CHECKING:
    from core.builtins.dispatcher import AbstractDispatcher
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["BaseExecutor", "HandlerExecutor", "JobExecutor"]

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


class BaseExecutor:
    """执行器
    Args:
        name(str): 该执行器的名称。执行器的名称是唯一的。

    只支持执行只拥有 POSITIONAL_OR_KEYWORD 和 KEYWORD_ONLY 两种参数类型的函数
    """

    _lock: ClassVar["LockType"] = Lock()
    _instances: ClassVar[Dict[str, Self]] = {}

    def __new__(cls, name: str, *args, **kwargs):
        with cls._lock:
            if (instance := cls._instances.get(name, None)) is None:
                instance = object.__new__(cls)
                instance.__init__(name, *args, **kwargs)
                cls._instances.update({name: instance})
        return instance

    @cached_property
    def name(self) -> str:
        """当前执行器的名称"""
        return self._name

    def __init__(self, name: str, dispatcher: Optional[Type["AbstractDispatcher"]] = None) -> None:
        self._name = name
        self._dispatcher = dispatcher

    async def __call__(
        self,
        target: Callable[P, R],
        block: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
        lock_id: int = None,
        **kwargs,
    ) -> R:
        from core.builtins.dispatcher import BaseDispatcher

        dispatcher = self._dispatcher or dispatcher or BaseDispatcher
        with (HashLock(lock_id or target) if block else do_nothing()):
            dispatcher_instance = dispatcher(**kwargs)
            dispatched_func = dispatcher_instance.dispatch(target)  # 分发参数，组成新函数

            # 执行
            if inspect.iscoroutinefunction(target):
                result = await dispatched_func()
            else:
                result = dispatched_func()

        return result


class HandlerExecutor(BaseExecutor, Generic[P, R]):
    """Handler专用执行器"""

    _callback: Callable[P, R]

    def __init__(self, func: Callable[P, R], dispatcher: Optional[Type["AbstractDispatcher"]] = None) -> None:
        if dispatcher is None:
            from core.builtins.dispatcher import HandlerDispatcher

            dispatcher = HandlerDispatcher
        super().__init__("handler", dispatcher)
        self._callback = func

    # noinspection PyMethodOverriding
    async def __call__(
        self,
        update: Update,
        context: CallbackContext,
        block: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
        lock_id: int = None,
        **kwargs,
    ) -> R:
        with handler_contexts(update, context):
            return await super().__call__(
                self._callback,
                dispatcher=dispatcher,
                block=block,
                lock_id=lock_id,
                update=update,
                context=context,
                **kwargs,
            )


class JobExecutor(BaseExecutor):
    """Job 专用执行器"""

    def __init__(self, func: Callable[P, R], dispatcher: Optional[Type["AbstractDispatcher"]] = None) -> None:
        if dispatcher is None:
            from core.builtins.dispatcher import JobDispatcher

            dispatcher = JobDispatcher
        super().__init__("job", dispatcher)
        self._callback = func

    async def __call__(
        self,
        context: CallbackContext,
        block: bool = False,
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
        lock_id: int = None,
        **kwargs,
    ) -> R:
        with job_contexts(context):
            return await super().__call__(
                self._callback,
                dispatcher=dispatcher,
                block=block,
                lock_id=lock_id,
                context=context,
                **kwargs,
            )
