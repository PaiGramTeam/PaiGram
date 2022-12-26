from functools import WRAPPER_ASSIGNMENTS as _WRAPPER_ASSIGNMENTS
from typing import List

from utils.const._path import *
from utils.const._single import *
from utils.const._url import *

NOT_SET = object()
# noinspection PyTypeChecker
WRAPPER_ASSIGNMENTS: List[str] = list(_WRAPPER_ASSIGNMENTS) + [
    "block",
    "_catch_target",
]
