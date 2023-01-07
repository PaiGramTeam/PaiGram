"""参数分发器"""
import inspect
from inspect import Signature, Parameter
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
    """参数分发器"""

    IGNORED_ATTRS = []

    _args: List[Any] = []
    _kwargs: Dict[Union[str, Type], Any] = {}

    def __init__(self, *args, **kwargs) -> None:
        self._args = list(args)
        self._kwargs = kwargs

        for key, value in self._kwargs:
            type_arg = type(value)
            if type_arg != str:
                if type_arg not in self._kwargs:
                    self._kwargs[type_arg] = value
                elif isinstance((arg_v := self._kwargs[type_arg]), list) and getattr(arg_v, "_is_arg_", False):
                    self._kwargs[type_arg] = [*arg_v, value]
                    setattr(self._kwargs[type_arg], "_is_arg_", True)
                else:
                    self._kwargs[type_arg] = [arg_v, value]
                    setattr(self._kwargs[type_arg], "_is_arg_", True)

        for arg in args:
            type_arg = type(arg)
            if type_arg != str:
                if type_arg not in self._kwargs:
                    self._kwargs[type_arg] = arg
                elif isinstance((arg_v := self._kwargs[type_arg]), list) and getattr(arg_v, "_is_arg_", False):
                    self._kwargs[type_arg] = [*arg_v, arg]
                    setattr(self._kwargs[type_arg], "_is_arg_", True)
                else:
                    self._kwargs[type_arg] = [arg_v, arg]
                    setattr(self._kwargs[type_arg], "_is_arg_", True)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._kwargs = {}

    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:

        params = {}
        if isinstance(func, type):
            signature: Signature = inspect.signature(func.__init__)
        else:
            signature: Signature = inspect.signature(func)
        parameters: Dict[str, Parameter] = dict(signature.parameters)
        for name, parameter in parameters.items():
            if isinstance(func, type) and parameter.name == "self":
                continue
            annotation = parameter.annotation
            for catch_func in self.catch_funcs:
                catch_targets = getattr(catch_func, "_catch_targets")
                for catch_target in catch_targets:
                    if isinstance(catch_target, str):
                        # 比较参数名
                        if any(
                            [name == catch_target, isinstance(annotation, type) and annotation.__name__ == catch_target]
                        ):
                            params[name] = catch_func()
                    # 比较参数类型
                    elif isinstance(catch_target, type) and any(
                        [
                            name == catch_target.__name__,
                            annotation.__name__ == catch_target.__name__,
                        ]
                    ):
                        params[name] = catch_func()

        params = {k: v for k, v in params.items() if v is not None}
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
    def __init__(self, update: Update, context: CallbackContext, **kwargs) -> None:
        super().__init__(update=update, contex=context, **kwargs)
        self._update = update
        self._context = context

    @catch(Update)
    def catch_update(self) -> Update:
        return self._update

    @catch(CallbackContext)
    def catch_context(self) -> CallbackContext:
        return self._context
