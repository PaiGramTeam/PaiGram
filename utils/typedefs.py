from pathlib import Path
from types import TracebackType
from typing import Any, Dict, Optional, Tuple, Type, Union

from httpx import URL

__all__ = [
    'StrOrPath', 'StrOrURL',
    'SysExcInfoType', 'ExceptionInfoType',
    'JSONDict',
]

StrOrPath = Union[str, Path]
StrOrURL = Union[str, URL]
SysExcInfoType = Union[
    Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
    Tuple[None, None, None]
]
ExceptionInfoType = Union[bool, SysExcInfoType, BaseException]
JSONDict = Dict[str, Any]
