from pathlib import Path
from types import TracebackType
from typing import Tuple, Type, Union, Dict, Any

__all__ = [
    'StrOrPath',
    'ExceptionInfoType',
    'JSONDict',
]

StrOrPath = Union[str, Path]
ExceptionInfoType = Union[bool, Tuple[Type[BaseException], BaseException, TracebackType, None], Tuple[None, None, None]]
JSONDict = Dict[str, Any]
