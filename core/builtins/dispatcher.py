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
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    TYPE_CHECKING,
    Type,
    TypeVar,
    Union,
    _GenericAlias as GenericAlias,
)

from arkowrapper import ArkoWrapper
from fastapi import FastAPI
from telegram import Bot as TGBot, Chat, Message, Update, User
from telegram.ext import Application as TGApplication, CallbackContext, Job
from typing_extensions import ParamSpec
from uvicorn import Server

from core.application import Application
from core.builtins.contexts import TGContext, TGUpdate
from core.config import ApplicationConfig, config as application_config
from utils.const import WRAPPER_ASSIGNMENTS
from utils.typedefs import R, T

__all__ = (
    "catch",
    "AbstractDispatcher",
    "BaseDispatcher",
    "HandlerDispatcher",
    "JobDispatcher",
    "ErrorHandlerDispatcher",
    "dispatched",
)

P = ParamSpec("P")

TargetType = Union[Type, str, Callable[[Any], bool]]

_default_kwargs: Dict[Type[T], T] = {}

_CATCH_TARGET_ATTR = "_catch_targets"


def catch(*targets: Union[str, Type]) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        setattr(func, _CATCH_TARGET_ATTR, targets)

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
    _application: "Optional[Application]" = None

    def set_application(self, application: "Application") -> None:
        self._application = application

    @property
    def application(self) -> "Application":
        if self._application is None:
            raise RuntimeError(f"No application was set for this {self.__class__.__name__}.")
        return self._application

    def __init__(self, *args, **kwargs) -> None:
        self._args = list(args)
        self._kwargs = dict(kwargs)

        for key, value in kwargs.items():
            type_arg = type(value)
            if type_arg != str:
                self._kwargs[type_arg] = value

        for arg in args:
            type_arg = type(arg)
            if type_arg != str:
                self._kwargs[type_arg] = arg

    @cached_property
    def catch_funcs(self) -> List[MethodType]:
        # noinspection PyTypeChecker
        return list(
            ArkoWrapper(dir(self))
            .filter(lambda x: not x.startswith("_"))
            .filter(lambda x: x not in self.IGNORED_ATTRS + ["dispatch", "catch_funcs", "catch_func_map"])
            .map(lambda x: getattr(self, x))
            .filter(lambda x: isinstance(x, MethodType))
            .filter(lambda x: hasattr(x, "_catch_targets"))
        )

    @cached_property
    def catch_func_map(self) -> Dict[Union[str, Type[T]], Callable[..., T]]:
        result = {}
        for catch_func in self.catch_funcs:
            catch_targets = getattr(catch_func, _CATCH_TARGET_ATTR)
            for catch_target in catch_targets:
                result[catch_target] = catch_func
                # if isinstance(catch_target, type):
                #     result[catch_target.__name__] = catch_func
        return result

    @abstractmethod
    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:
        """将参数分配给函数，从而合成一个无需参数即可执行的函数"""


class BaseDispatcher(AbstractDispatcher):
    """默认参数分发器"""

    _instances: Sequence[Any]

    def _get_kwargs(self) -> Dict[Type[T], T]:
        result = self._get_default_kwargs()
        result[AbstractDispatcher] = self
        result.update(self._kwargs)
        return result

    def _get_default_kwargs(self) -> Dict[Type[T], T]:
        application = self.application
        _default_kwargs = {
            Application: application,
            TGBot: application.telegram.bot,
            type(application.managers.executor): application.managers.executor,
            FastAPI: application.web_app if application_config.webserver.switch else None,
            Server: application.web_server if application_config.webserver.switch else None,
            TGApplication: application.telegram,
            ApplicationConfig: application_config,
        }
        if not application.running:
            for obj in chain(
                application.managers.dependency,
                application.managers.components,
                application.managers.services,
                application.managers.plugins,
            ):
                _default_kwargs[type(obj)] = obj
        return {k: v for k, v in _default_kwargs.items() if v is not None}

    def dispatch(self, func: Callable[P, R]) -> Callable[..., R]:
        """分发参数给 func"""
        params = {}
        if isinstance(func, type):
            signature: Signature = inspect.signature(func.__init__)
        else:
            signature: Signature = inspect.signature(func)
        parameters: Dict[str, Parameter] = dict(signature.parameters)

        for name, parameter in signature.parameters.items():
            if any(
                [
                    name == "self" and isinstance(func, (type, MethodType)),
                    parameter.kind in [Parameter.VAR_KEYWORD, Parameter.VAR_POSITIONAL],
                ]
            ):
                del parameters[name]
                continue
            annotation = parameter.annotation
            # noinspection PyTypeChecker
            if isinstance(annotation, type) and (value := self._get_kwargs().get(annotation, None)) is not None:
                params[name] = value

        for name, parameter in list(parameters.items()):
            annotation = parameter.annotation
            if annotation != Any and isinstance(annotation, GenericAlias):
                continue

            catch_func = self.catch_func_map.get(annotation, None) or self.catch_func_map.get(name, None)
            if catch_func is not None:
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
    """Handler 参数分发器"""

    def __init__(self, update: Optional[Update] = None, context: Optional[CallbackContext] = None, **kwargs) -> None:
        update = update or TGUpdate.get()
        context = context or TGContext.get()
        super().__init__(update=update, context=context, **kwargs)
        self._update = update
        self._context = context

    @catch(Update)
    def catch_update(self) -> Update:
        return self._update

    @catch(CallbackContext)
    def catch_context(self) -> CallbackContext:
        return self._context

    @catch(Message)
    def catch_message(self) -> Message:
        return self._update.effective_message

    @catch(User)
    def catch_user(self) -> User:
        return self._update.effective_user

    @catch(Chat)
    def catch_chat(self) -> Chat:
        return self._update.effective_chat


class ErrorHandlerDispatcher(HandlerDispatcher):
    @catch(Exception)
    def catch_error(self) -> Exception:
        return self._context.error


class JobDispatcher(BaseDispatcher):
    """Job 参数分发器"""

    def __init__(self, context: Optional[CallbackContext] = None, **kwargs) -> None:
        context = context or TGContext.get()
        super().__init__(context=context, **kwargs)
        self._context = context

    @catch("data")
    def catch_data(self) -> Any:
        return self._context.job.data

    @catch(Job)
    def catch_job(self) -> Job:
        return self._context.job


def dispatched(dispatcher: Type[AbstractDispatcher] = BaseDispatcher):
    def decorate(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return dispatcher().dispatch(func)(*args, **kwargs)

        return wrapper

    return decorate
