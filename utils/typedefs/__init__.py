import sys
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING, Tuple, Type, Union

from utils.typedefs._generics import *
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
    # queue
    "BaseQueue",
    "SyncQueue",
    "AsyncQueue",
    # generics
    "P",
    "T",
    "R",
]

if TYPE_CHECKING:
    from pathlib import Path
    from httpx import URL
    from logging import Filter, LogRecord
    from pydantic import ConstrainedInt
    from types import TracebackType

    StrOrPath = Union[str, Path]
    StrOrURL = Union[str, URL]
    LogFilterType = Union[Filter, Callable[[LogRecord], int]]

    SysExcInfoType = Union[Tuple[Type[BaseException], BaseException, Optional[TracebackType]], Tuple[None, None, None]]

    class NaturalNumber(ConstrainedInt):
        """自然数"""

        ge = 0

else:
    StrOrPath = Union[str, "Path"]
    StrOrURL = Union[str, "URL"]
    LogFilterType = Union["Filter", Callable[["LogRecord"], int]]
    SysExcInfoType = Union[
        Tuple[Type[BaseException], BaseException, Optional["TracebackType"]], Tuple[None, None, None]
    ]
    NaturalNumber = int

StrOrInt = Union[str, int]

ExceptionInfoType = Union[bool, SysExcInfoType, BaseException]
JSONDict = Dict[str, Any]
JSONType = Union[JSONDict, list]
