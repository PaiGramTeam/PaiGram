"""参数分发器"""
import asyncio
import inspect
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop
from functools import cached_property, partial, wraps
from inspect import Parameter, Signature
from itertools import chain
from types import MethodType

# noinspection PyUnresolvedReferences,PyProtectedMember
from typing import Any, Callable, Dict, List, Sequence, Type, TypeVar, Union, _GenericAlias as GenericAlias

from arkowrapper import ArkoWrapper
from fastapi import FastAPI
from telegram import Update
from telegram.ext import Application as TGApplication, CallbackContext
from typing_extensions import ParamSpec
from uvicorn import Server

from core.bot import Bot, bot
from core.config import BotConfig, config as bot_config
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
    """默认参数分发器"""

    _instances: Sequence[Any]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_kwargs(self) -> Dict[Type[T], T]:

        result = {
            AbstractDispatcher: self,
            Bot: bot,
            type(bot.executor): bot.executor,
            FastAPI: bot.web_app,
            Server: bot.web_server,
            TGApplication: bot.tg_app,
            BotConfig: bot_config,
        }
        result.update(self._kwargs)
        for item in chain(bot.dependency, bot.components, bot.services):
            result[type(item)] = item
        return result

    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:
        params = {}
        if isinstance(func, type):
            signature: Signature = inspect.signature(func.__init__)
        else:
            signature: Signature = inspect.signature(func)
        parameters: Dict[str, Parameter] = dict(signature.parameters)

        for name, parameter in signature.parameters.items():
            if isinstance(func, type) and name == "self":
                del parameters[name]
                continue
            annotation = parameter.annotation
            # noinspection PyTypeChecker
            if isinstance(annotation, type) and (value := self._get_kwargs().get(annotation, None)) is not None:
                params[name] = value

        for name, parameter in list(parameters.items()):
            annotation = parameter.annotation
            if isinstance(annotation, GenericAlias):
                continue
            for catch_func in self.catch_funcs:
                catch_targets = getattr(catch_func, "_catch_targets")
                for catch_target in catch_targets:
                    if isinstance(catch_target, str):
                        # 比较参数名
                        if any(
                            [name == catch_target, isinstance(annotation, type) and annotation.__name__ == catch_target]
                        ):
                            params[name] = catch_func()
                            del parameters[name]
                    # 比较参数类型
                    elif isinstance(catch_target, type) and any(
                        [
                            name == catch_target.__name__,
                            annotation.__name__ == catch_target.__name__,
                        ]
                    ):
                        params[name] = catch_func()
                        del parameters[name]

        for name, parameter in parameters.items():
            if name in params:
                continue
            if parameter.default != Parameter.empty:
                params[name] = parameter.default
            else:
                params[name] = None

        return partial(func, **params)

    @catch(AbstractEventLoop)
    def catch_loop(self) -> AbstractEventLoop:

        return asyncio.get_event_loop()


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
