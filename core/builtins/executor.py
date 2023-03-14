"""执行器"""
import inspect
from functools import cached_property
from multiprocessing import RLock as Lock
from typing import Callable, ClassVar, Dict, Generic, Optional, TYPE_CHECKING, Type, TypeVar

from telegram import Update
from telegram.ext import CallbackContext
from typing_extensions import ParamSpec, Self

from core.builtins.contexts import handler_contexts, job_contexts

if TYPE_CHECKING:
    from core.application import Application
    from core.builtins.dispatcher import AbstractDispatcher, HandlerDispatcher
    from multiprocessing.synchronize import RLock as LockType

__all__ = ("BaseExecutor", "Executor", "HandlerExecutor", "JobExecutor")

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
    _application: "Optional[Application]" = None

    def set_application(self, application: "Application") -> None:
        self._application = application

    @property
    def application(self) -> "Application":
        if self._application is None:
            raise RuntimeError(f"No application was set for this {self.__class__.__name__}.")
        return self._application

    def __new__(cls: Type[T], name: str, *args, **kwargs) -> T:
        with cls._lock:
            if (instance := cls._instances.get(name)) is None:
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


class Executor(BaseExecutor, Generic[P, R]):
    async def __call__(
        self,
        target: Callable[P, R],
        dispatcher: Optional[Type["AbstractDispatcher"]] = None,
        **kwargs,
    ) -> R:
        dispatcher = self._dispatcher or dispatcher
        dispatcher_instance = dispatcher(**kwargs)
        dispatcher_instance.set_application(application=self.application)
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
    _dispatcher: "HandlerDispatcher"

    def __init__(self, func: Callable[P, R], dispatcher: Optional[Type["HandlerDispatcher"]] = None) -> None:
        if dispatcher is None:
            from core.builtins.dispatcher import HandlerDispatcher

            dispatcher = HandlerDispatcher
        super().__init__("handler", dispatcher)
        self._callback = func
        self._dispatcher = dispatcher()

    def set_application(self, application: "Application") -> None:
        self._application = application
        if self._dispatcher is not None:
            self._dispatcher.set_application(application)

    async def __call__(self, update: Update, context: CallbackContext) -> R:
        with handler_contexts(update, context):
            dispatched_func = self._dispatcher.dispatch(self._callback, update=update, context=context)
            return await dispatched_func()


class JobExecutor(BaseExecutor):
    """Job 专用执行器"""

    def __init__(self, func: Callable[P, R], dispatcher: Optional[Type["AbstractDispatcher"]] = None) -> None:
        if dispatcher is None:
            from core.builtins.dispatcher import JobDispatcher

            dispatcher = JobDispatcher
        super().__init__("job", dispatcher)
        self._callback = func
        self._dispatcher = dispatcher()

    def set_application(self, application: "Application") -> None:
        self._application = application
        if self._dispatcher is not None:
            self._dispatcher.set_application(application)

    async def __call__(self, context: CallbackContext) -> R:
        with job_contexts(context):
            dispatched_func = self._dispatcher.dispatch(self._callback, context=context)
            return await dispatched_func()
