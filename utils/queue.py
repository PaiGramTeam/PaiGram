"""线程安全的队列"""

import asyncio
import sys
from asyncio import (
    Future,
    QueueEmpty as AsyncQueueEmpty,
    QueueFull as AsyncQueueFull,
)
from collections import deque
from heapq import (
    heappop,
    heappush,
)
from queue import (
    Empty as SyncQueueEmpty,
    Full as SyncQueueFull,
)
from threading import (
    Condition,
    Lock,
)
from typing import (
    Any,
    Callable,
    Deque,
    Generic,
    List,
    NoReturn,
    Optional,
    Set,
    TYPE_CHECKING,
    TypeVar,
)

from utils.typedefs import (
    AsyncQueue,
    SyncQueue,
)

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop as EventLoop

__all__ = (
    "Queue",
    "PriorityQueue",
    "LifoQueue",
)

T = TypeVar("T")
OptFloat = Optional[float]


class Queue(Generic[T]):
    """线程安全的同步、异步队列"""

    _loop: "EventLoop"

    @property
    def loop(self) -> "EventLoop":
        """返回该队列的事件循环"""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError("没有正在运行的事件循环, 请在异步函数中使用.")
        return self._loop

    def __init__(self, maxsize: int = 0) -> NoReturn:
        """初始化队列

        Args:
            maxsize (int): 队列的大小
        Returns:
            无
        """
        self._maxsize = maxsize

        self._init(maxsize)

        self._unfinished_tasks = 0

        self._sync_mutex = Lock()
        self._sync_not_empty = Condition(self._sync_mutex)
        self._sync_not_full = Condition(self._sync_mutex)
        self._all_tasks_done = Condition(self._sync_mutex)

        self._async_mutex = asyncio.Lock()
        if sys.version_info[:3] == (3, 10, 0):
            # 针对 3.10 的 bug
            getattr(self._async_mutex, "_get_loop", lambda: None)()
        self._async_not_empty = asyncio.Condition(self._async_mutex)
        self._async_not_full = asyncio.Condition(self._async_mutex)
        self._finished = asyncio.Event()
        self._finished.set()

        self._closing = False
        self._pending: Set[Future[Any]] = set()

        def checked_call_soon_threadsafe(callback: Callable[..., None], *args: Any) -> NoReturn:
            try:
                self.loop.call_soon_threadsafe(callback, *args)
            except RuntimeError:
                pass

        self._call_soon_threadsafe = checked_call_soon_threadsafe

        def checked_call_soon(callback: Callable[..., None], *args: Any) -> NoReturn:
            if not self.loop.is_closed():
                self.loop.call_soon(callback, *args)

        self._call_soon = checked_call_soon

        self._sync_queue = _SyncQueueProxy(self)
        self._async_queue = _AsyncQueueProxy(self)

    def close(self) -> NoReturn:
        """关闭队列"""
        with self._sync_mutex:
            self._closing = True
            for fut in self._pending:
                fut.cancel()
            self._finished.set()  # 取消堵塞全部的 async_q.join()
            self._all_tasks_done.notify_all()  # 取消堵塞全部的 sync_q.join()

    async def wait_closed(self) -> NoReturn:
        if not self._closing:
            raise RuntimeError("队列已被关闭")
        await asyncio.sleep(0)
        if not self._pending:
            return
        await asyncio.wait(self._pending)

    @property
    def closed(self) -> bool:
        return self._closing and not self._pending

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def sync_q(self) -> "_SyncQueueProxy[T]":
        return self._sync_queue

    @property
    def async_q(self) -> "_AsyncQueueProxy[T]":
        return self._async_queue

    def _init(self, maxsize: int) -> NoReturn:
        self._queue = deque()  # type: Deque[T]

    def _qsize(self) -> int:
        return len(self._queue)

    def _put(self, item: T) -> NoReturn:
        self._queue.append(item)

    def _get(self) -> T:
        return self._queue.popleft()

    def _put_internal(self, item: T) -> NoReturn:
        self._put(item)
        self._unfinished_tasks += 1
        self._finished.clear()

    def _notify_sync_not_empty(self) -> NoReturn:
        def f() -> NoReturn:
            with self._sync_mutex:
                self._sync_not_empty.notify()

        self.loop.run_in_executor(None, f)

    def _notify_sync_not_full(self) -> NoReturn:
        def f() -> NoReturn:
            with self._sync_mutex:
                self._sync_not_full.notify()

        fut = asyncio.ensure_future(self.loop.run_in_executor(None, f))
        fut.add_done_callback(self._pending.discard)
        self._pending.add(fut)

    def _notify_async_not_empty(self, *, threadsafe: bool) -> NoReturn:
        async def f() -> NoReturn:
            async with self._async_mutex:
                self._async_not_empty.notify()

        def task_maker() -> NoReturn:
            task = self.loop.create_task(f())
            task.add_done_callback(self._pending.discard)
            self._pending.add(task)

        if threadsafe:
            self._call_soon_threadsafe(task_maker)
        else:
            self._call_soon(task_maker)

    def _notify_async_not_full(self, *, threadsafe: bool) -> NoReturn:
        async def f() -> NoReturn:
            async with self._async_mutex:
                self._async_not_full.notify()

        def task_maker() -> NoReturn:
            task = self.loop.create_task(f())
            task.add_done_callback(self._pending.discard)
            self._pending.add(task)

        if threadsafe:
            self._call_soon_threadsafe(task_maker)
        else:
            self._call_soon(task_maker)

    def _check_closing(self) -> NoReturn:
        if self._closing:
            raise RuntimeError("禁止对已关闭的队列进行操作")


# noinspection PyProtectedMember
class _SyncQueueProxy(SyncQueue[T]):
    """同步"""

    def __init__(self, parent: Queue[T]):
        self._parent = parent

    @property
    def maxsize(self) -> int:
        return self._parent._maxsize

    @property
    def closed(self) -> bool:
        return self._parent.closed

    def task_done(self) -> NoReturn:
        self._parent._check_closing()
        with self._parent._all_tasks_done:
            unfinished = self._parent._unfinished_tasks - 1
            if unfinished <= 0:
                if unfinished < 0:
                    raise ValueError("task_done() 执行次数过多")
                self._parent._all_tasks_done.notify_all()
                self._parent.loop.call_soon_threadsafe(self._parent._finished.set)
            self._parent._unfinished_tasks = unfinished

    def join(self) -> NoReturn:
        self._parent._check_closing()
        with self._parent._all_tasks_done:
            while self._parent._unfinished_tasks:
                self._parent._all_tasks_done.wait()
                self._parent._check_closing()

    def qsize(self) -> int:
        """返回队列的大致大小（不可靠）"""
        return self._parent._qsize()

    @property
    def unfinished_tasks(self) -> int:
        """返回未完成 task 的数量"""
        return self._parent._unfinished_tasks

    def empty(self) -> bool:
        return not self._parent._qsize()

    def full(self) -> bool:
        return 0 < self._parent._maxsize <= self._parent._qsize()

    def put(self, item: T, block: bool = True, timeout: OptFloat = None) -> NoReturn:
        self._parent._check_closing()
        with self._parent._sync_not_full:
            if self._parent._maxsize > 0:
                if not block:
                    if self._parent._qsize() >= self._parent._maxsize:
                        raise SyncQueueFull
                elif timeout is None:
                    while self._parent._qsize() >= self._parent._maxsize:
                        self._parent._sync_not_full.wait()
                elif timeout < 0:
                    raise ValueError("'timeout' 必须为一个非负数")
                else:
                    time = self._parent.loop.time
                    end_time = time() + timeout
                    while self._parent._qsize() >= self._parent._maxsize:
                        remaining = end_time - time()
                        if remaining <= 0.0:
                            raise SyncQueueFull
                        self._parent._sync_not_full.wait(remaining)
            self._parent._put_internal(item)
            self._parent._sync_not_empty.notify()
            self._parent._notify_async_not_empty(threadsafe=True)

    def get(self, block: bool = True, timeout: OptFloat = None) -> T:
        self._parent._check_closing()
        with self._parent._sync_not_empty:
            if not block:
                if not self._parent._qsize():
                    raise SyncQueueEmpty
            elif timeout is None:
                while not self._parent._qsize():
                    self._parent._sync_not_empty.wait()
            elif timeout < 0:
                raise ValueError("'timeout' 必须为一个非负数")
            else:
                time = self._parent.loop.time
                end_time = time() + timeout
                while not self._parent._qsize():
                    remaining = end_time - time()
                    if remaining <= 0.0:
                        raise SyncQueueEmpty
                    self._parent._sync_not_empty.wait(remaining)
            item = self._parent._get()
            self._parent._sync_not_full.notify()
            self._parent._notify_async_not_full(threadsafe=True)
            return item

    def put_nowait(self, item: T) -> NoReturn:
        return self.put(item, block=False)

    def get_nowait(self) -> T:
        return self.get(block=False)


# noinspection PyProtectedMember
class _AsyncQueueProxy(AsyncQueue[T]):
    """异步"""

    def __init__(self, parent: Queue[T]):
        self._parent = parent

    @property
    def closed(self) -> bool:
        return self._parent.closed

    def qsize(self) -> int:
        return self._parent._qsize()

    @property
    def unfinished_tasks(self) -> int:
        return self._parent._unfinished_tasks

    @property
    def maxsize(self) -> int:
        return self._parent._maxsize

    def empty(self) -> bool:
        return self.qsize() == 0

    def full(self) -> bool:
        if self._parent._maxsize <= 0:
            return False
        else:
            return self.qsize() >= self._parent._maxsize

    async def put(self, item: T) -> None:
        self._parent._check_closing()
        async with self._parent._async_not_full:
            self._parent._sync_mutex.acquire()
            locked = True
            try:
                if self._parent._maxsize > 0:
                    do_wait = True
                    while do_wait:
                        do_wait = self._parent._qsize() >= self._parent._maxsize
                        if do_wait:
                            locked = False
                            self._parent._sync_mutex.release()
                            await self._parent._async_not_full.wait()
                            self._parent._sync_mutex.acquire()
                            locked = True

                self._parent._put_internal(item)
                self._parent._async_not_empty.notify()
                self._parent._notify_sync_not_empty()
            finally:
                if locked:
                    self._parent._sync_mutex.release()

    def put_nowait(self, item: T) -> NoReturn:
        self._parent._check_closing()
        with self._parent._sync_mutex:
            if self._parent._maxsize > 0:
                if self._parent._qsize() >= self._parent._maxsize:
                    raise AsyncQueueFull

            self._parent._put_internal(item)
            self._parent._notify_async_not_empty(threadsafe=False)
            self._parent._notify_sync_not_empty()

    async def get(self) -> T:
        self._parent._check_closing()
        async with self._parent._async_not_empty:
            self._parent._sync_mutex.acquire()
            locked = True
            try:
                do_wait = True
                while do_wait:
                    do_wait = self._parent._qsize() == 0

                    if do_wait:
                        locked = False
                        self._parent._sync_mutex.release()
                        await self._parent._async_not_empty.wait()
                        self._parent._sync_mutex.acquire()
                        locked = True

                item = self._parent._get()
                self._parent._async_not_full.notify()
                self._parent._notify_sync_not_full()
                return item
            finally:
                if locked:
                    self._parent._sync_mutex.release()

    def get_nowait(self) -> T:
        self._parent._check_closing()
        with self._parent._sync_mutex:
            if self._parent._qsize() == 0:
                raise AsyncQueueEmpty

            item = self._parent._get()
            self._parent._notify_async_not_full(threadsafe=False)
            self._parent._notify_sync_not_full()
            return item

    def task_done(self) -> NoReturn:
        self._parent._check_closing()
        with self._parent._all_tasks_done:
            if self._parent._unfinished_tasks <= 0:
                raise ValueError("task_done() called too many times")
            self._parent._unfinished_tasks -= 1
            if self._parent._unfinished_tasks == 0:
                self._parent._finished.set()
                self._parent._all_tasks_done.notify_all()

    async def join(self) -> None:
        while True:
            with self._parent._sync_mutex:
                self._parent._check_closing()
                if self._parent._unfinished_tasks == 0:
                    break
            await self._parent._finished.wait()


class PriorityQueue(Queue[T]):
    """优先级队列"""

    def _init(self, maxsize: int) -> NoReturn:
        self._heap_queue: List[T] = []

    def _qsize(self) -> int:
        return len(self._heap_queue)

    def _put(self, item: T) -> NoReturn:
        if not isinstance(item, tuple):
            if hasattr(item, "priority"):
                item = (int(item.priority), item)
            else:
                try:
                    item = (int(item), item)
                except (TypeError, ValueError):
                    pass
        heappush(self._heap_queue, item)

    def _get(self) -> T:
        return heappop(self._heap_queue)


class LifoQueue(Queue[T]):
    """后进先出队列"""

    def _qsize(self) -> int:
        return len(self._queue)

    def _put(self, item: T) -> NoReturn:
        self._queue.append(item)

    def _get(self) -> T:
        return self._queue.pop()
