import sys
from typing import TypeVar

__all__ = ("T", "R", "P")

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

T = TypeVar("T")  # normal type
R = TypeVar("R")  # return type
P = ParamSpec("P")  # param type
