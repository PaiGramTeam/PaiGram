import sys
from logging import Filter, LogRecord
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

from httpx import URL
from pydantic import ConstrainedInt

from utils.typedefs._queue import AsyncQueue, BaseQueue, SyncQueue

if sys.version_info >= (3, 9):
    from types import GenericAlias
else:
    # noinspection PyUnresolvedReferences,PyProtectedMember
    from typing import _GenericAlias as GenericAlias

__all__ = [
    "GenericAlias",
    "StrOrPath",
    "StrOrURL",
    "StrOrInt",
    "SysExcInfoType",
    "ExceptionInfoType",
    "JSONDict",
    "JSONType",
    "LogFilterType",
    "NaturalNumber",
    "BaseQueue",
    "SyncQueue",
    "AsyncQueue",
]

StrOrPath = Union[str, Path]
StrOrURL = Union[str, URL]
StrOrInt = Union[str, int]

SysExcInfoType = Union[Tuple[Type[BaseException], BaseException, Optional[TracebackType]], Tuple[None, None, None]]
ExceptionInfoType = Union[bool, SysExcInfoType, BaseException]
JSONDict = Dict[str, Any]
JSONType = Union[JSONDict, list]

LogFilterType = Union[Filter, Callable[[LogRecord], int]]


class NaturalNumber(ConstrainedInt):
    ge = 0
