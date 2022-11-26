import inspect
from functools import partial
from multiprocessing import RLock as Lock
from typing import (TYPE_CHECKING, Any, Callable, ClassVar, Dict, Mapping,
                    Sequence, Type, TypeVar)

from telegram.ext import CallbackContext
# noinspection PyProtectedMember
from telegram.ext._utils.types import HandlerCallback
from typing_extensions import ParamSpec, Self

from utils.helpers import do_nothing
from utils.models.lock import HashLock

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["Executor"]

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


def get_bot_type_args() -> Dict[Type[T], T]:
    from core.bot import bot

    return {
        type(bot): bot,
        type(bot.tg_app): bot.tg_app,
        type(bot.web_app): bot.web_app,
        type(bot.web_server): bot.web_server,
    }


def get_bot_str_args() -> Dict[str, Any]:
    from core.bot import bot

    return {
        "bot": bot,
        "tg_app": bot.tg_app,
        "web_app": bot.web_app,
        "web_server": bot.web_server,
    }


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

    def __init__(self, name: str):
        self._name = name

    async def __call__(
        self,
        target: Callable[P, R],
        block: bool = False,
        *,
        args: Sequence = None,
        kwargs: Mapping = None,
        lock_id: int = None,
    ) -> R:
        args = args or []
        kwargs = kwargs or {}

        with (HashLock(lock_id or target) if block else do_nothing()):
            arg_map = {}

            type_args_map = {
                **get_bot_type_args(),
                **{k: v for k, v in kwargs.items() if isinstance(k, type)},
                **{type(arg): arg for arg in args},
            }
            str_args_map = {
                **get_bot_str_args(),
                **{k: v for k, v in kwargs.items() if isinstance(k, str)},
            }

            signature = inspect.signature(target)
            for name, parameter in signature.parameters.items():
                annotation = parameter.annotation
                if isinstance(annotation, str) and name in str_args_map:
                    arg_map.update({name: str_args_map.get(name)})
                elif annotation in type_args_map:
                    arg_map.update({name: type_args_map.get(annotation)})

            wrapped_func = partial(target, **arg_map)

            if inspect.iscoroutinefunction(target):
                result = await wrapped_func()
            else:
                result = wrapped_func()

        return result


class HandlerExecutor:
    def __init__(self, func: Callable[P, R]) -> None:
        self.callback = func
        self.executor = Executor("handler")

    async def __call__(self, callback: HandlerCallback, context: CallbackContext) -> R:
        return await self.executor(self.callback, args=(callback, context))


def main():
    executor_a = Executor("a")
    executor_b = Executor("a")
    print(executor_a == executor_b)


if __name__ == "__main__":
    main()
