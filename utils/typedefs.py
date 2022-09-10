from pathlib import Path
from types import TracebackType
from typing import Optional, Tuple, Type, Union, Dict, Any

__all__ = [
    'StrOrPath',
    'SysExcInfoType', 'ExceptionInfoType',
    'JSONDict',
]

StrOrPath = Union[str, Path]
SysExcInfoType = Union[
    Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
    Tuple[None, None, None]
]
ExceptionInfoType = Union[bool, SysExcInfoType, BaseException]
JSONDict = Dict[str, Any]
