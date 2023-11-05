# pylint: disable=W0049
from typing import Optional, Protocol, TypeVar

__all__ = ["BaseQueue", "SyncQueue", "AsyncQueue"]

T = TypeVar("T")


# noinspection PyPropertyDefinition
class BaseQueue(Protocol[T]):  # pylint: disable=W0049
    @property
    def maxsize(self) -> int:
        raise NotImplementedError

    @property
    def closed(self) -> bool:
        raise NotImplementedError

    def task_done(self):
        raise NotImplementedError()

    def qsize(self) -> int:
        raise NotImplementedError()

    @property
    def unfinished_tasks(self) -> int:
        raise NotImplementedError

    def empty(self) -> bool:
        raise NotImplementedError()

    def full(self) -> bool:
        raise NotImplementedError()

    def put_nowait(self, item: T) -> None:
        raise NotImplementedError()

    def get_nowait(self) -> T:
        raise NotImplementedError()


# noinspection PyPropertyDefinition
class SyncQueue(BaseQueue[T], Protocol[T]):  # pylint: disable=W0049
    @property
    def maxsize(self) -> int:
        raise NotImplementedError

    @property
    def closed(self) -> bool:
        raise NotImplementedError

    def task_done(self):
        raise NotImplementedError()

    def qsize(self) -> int:
        raise NotImplementedError()

    @property
    def unfinished_tasks(self) -> int:
        raise NotImplementedError

    def empty(self) -> bool:
        raise NotImplementedError()

    def full(self) -> bool:
        raise NotImplementedError()

    def put_nowait(self, item: T) -> None:
        raise NotImplementedError()

    def get_nowait(self) -> T:
        raise NotImplementedError()

    def put(self, item: T, block: bool = True, timeout: Optional[float] = None) -> None:
        raise NotImplementedError()

    def get(self, block: bool = True, timeout: Optional[float] = None) -> T:
        raise NotImplementedError()

    def join(self) -> None:
        raise NotImplementedError()


class AsyncQueue(BaseQueue[T], Protocol[T]):  # pylint: disable=W0049
    async def put(self, item: T) -> None:
        pass

    async def get(self) -> T:
        pass

    async def join(self) -> None:
        pass
