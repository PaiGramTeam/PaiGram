from multiprocessing import RLock as Lock
from typing import (
    Any,
    Dict,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["HashLock"]

_locks: Dict[int, "LockType"] = {}


class HashLock(object):
    """可以根据 hash 来获取锁的类"""

    target: int

    @property
    def lock(self) -> "LockType":
        # noinspection PyTypeChecker
        return _locks[self.target]

    def __init__(self, target: Any) -> None:
        if not isinstance(target, int):
            target = hash(target)
        if target not in _locks:
            # noinspection PyTypeChecker
            _locks[target] = Lock()
        self.target = target

    def __enter__(self) -> None:
        # noinspection PyTypeChecker
        return self.lock.__enter__()

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        return self.lock.__exit__(exc_type, exc_val, exc_tb)
