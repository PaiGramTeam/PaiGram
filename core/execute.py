import inspect
from functools import partial
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Sequence,
    Type,
    TypeVar,
)

from typing_extensions import ParamSpec

from core.bot import bot
from utils.models.lock import HashLock

__all__ = ["Executor"]

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


def get_bot_type_args() -> Dict[Type[T], T]:
    return {
        type(bot): bot,
        type(bot.tg_app): bot.tg_app,
        type(bot.web_app): bot.web_app,
        type(bot.web_server): bot.web_server,
    }


def get_bot_str_args() -> Dict[str, Any]:
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

        if block:
            HashLock(lock_id or target).__enter__()

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

        if block:
            HashLock(lock_id or target).__exit__()
        return result
