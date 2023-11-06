import asyncio
from asyncio import Task
from multiprocessing import RLock as Lock
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ("HashLock",)

_lock: "LockType" = Lock()
_locks: Dict[int, "LockType"] = {}
_clean_lock_task_map: Dict[int, Task] = {}


async def delete_lock(target: int) -> None:
    await asyncio.sleep(3)
    with _lock:
        del _locks[target]
        del _clean_lock_task_map[target]  # pylint: disable=E0602


class HashLock:
    """可以根据 hash 来获取锁的类"""

    target: int

    @property
    def lock(self) -> "LockType":
        # noinspection PyTypeChecker
        with _lock:
            if self.target not in _locks:
                # noinspection PyTypeChecker
                _locks[self.target] = Lock()
            else:
                _clean_lock_task_map[self.target].cancel()
            _clean_lock_task_map.update({self.target: asyncio.create_task(delete_lock(self.target))})
            return _locks[self.target]

    def __init__(self, target: Any) -> None:
        if not isinstance(target, int):
            target = hash(target)
        self.target = target

    def __enter__(self) -> bool:
        # noinspection PyTypeChecker
        return self.lock.__enter__()

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        return self.lock.__exit__(exc_type, exc_val, exc_tb)
