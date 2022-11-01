from typing import (
    NoReturn,
    Optional,
    Protocol,
    TypeVar,
)

__all__ = ['BaseQueue', 'SyncQueue', 'AsyncQueue']

T = TypeVar('T')


# noinspection PyPropertyDefinition
class BaseQueue(Protocol[T]):
    @property
    def maxsize(self) -> int: pass

    @property
    def closed(self) -> bool: pass

    def task_done(self) -> NoReturn: pass

    def qsize(self) -> int: pass

    @property
    def unfinished_tasks(self) -> int: pass

    def empty(self) -> bool: pass

    def full(self) -> bool: pass

    def put_nowait(self, item: T) -> None: pass

    def get_nowait(self) -> T: pass


# noinspection PyPropertyDefinition
class SyncQueue(BaseQueue[T], Protocol[T]):
    @property
    def maxsize(self) -> int: pass

    @property
    def closed(self) -> bool: pass

    def task_done(self) -> NoReturn: pass

    def qsize(self) -> int: pass

    @property
    def unfinished_tasks(self) -> int: pass

    def empty(self) -> bool: pass

    def full(self) -> bool: pass

    def put_nowait(self, item: T) -> None: pass

    def get_nowait(self) -> T: pass

    def put(
            self, item: T, block: bool = True, timeout: Optional[float] = None
    ) -> None: pass

    def get(self, block: bool = True, timeout: Optional[float] = None) -> T: pass

    def join(self) -> None: pass


class AsyncQueue(BaseQueue[T], Protocol[T]):
    async def put(self, item: T) -> None: pass

    async def get(self) -> T: pass

    async def join(self) -> None: pass
