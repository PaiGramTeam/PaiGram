from pathlib import Path
from types import TracebackType
from typing import Tuple, Type, Union

__all__ = [
    'StrOrPath',
    'ExceptionInfoType',
]

StrOrPath = Union[str, Path]
ExceptionInfoType = Union[bool, Tuple[Type[BaseException], BaseException, TracebackType, None], Tuple[None, None, None]]
