"""线程安全的队列"""

import asyncio
import sys
from asyncio import QueueEmpty as AsyncQueueEmpty
from asyncio import QueueFull as AsyncQueueFull
from collections import deque
from heapq import heappop, heappush
from queue import Empty as SyncQueueEmpty
from queue import Full as SyncQueueFull
from threading import Condition, Lock
from typing import TYPE_CHECKING, Any, Callable, Deque, Generic, List, NoReturn, Optional, Set, TypeVar

from utils.typedefs import AsyncQueue, SyncQueue

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
        except RuntimeError as e:
            raise RuntimeError("没有正在运行的事件循环, 请在异步函数中使用.") from e
        return self._loop

    def __init__(self, maxsize: int = 0):
        """初始化队列

        Args:
            maxsize (int): 队列的大小
        Returns:
            无
        """
        self._maxsize = maxsize

        self._init()

        self.unfinished_tasks = 0

        self.sync_mutex = Lock()
        self.sync_not_empty = Condition(self.sync_mutex)
        self.sync_not_full = Condition(self.sync_mutex)
        self.all_tasks_done = Condition(self.sync_mutex)

        self.async_mutex = asyncio.Lock()
        if sys.version_info[:3] == (3, 10, 0):
            # 针对 3.10 的 bug
            getattr(self.async_mutex, "_get_loop", lambda: None)()
        self.async_not_empty = asyncio.Condition(self.async_mutex)
        self.async_not_full = asyncio.Condition(self.async_mutex)
        self.finished = asyncio.Event()
        self.finished.set()

        self.closing = False
        self.pending = set()  # type: Set[asyncio.Future[Any]]

        def checked_call_soon_threadsafe(callback: Callable[..., None], *args: Any):
            try:
                self.loop.call_soon_threadsafe(callback, *args)
            except RuntimeError:
                pass

        self._call_soon_threadsafe = checked_call_soon_threadsafe

        def checked_call_soon(callback: Callable[..., None], *args: Any):
            if not self.loop.is_closed():
                self.loop.call_soon(callback, *args)

        self._call_soon = checked_call_soon

        self._sync_queue = _SyncQueueProxy(self)
        self._async_queue = _AsyncQueueProxy(self)

    def close(self):
        """关闭队列"""
        with self.sync_mutex:
            self.closing = True
            for fut in self.pending:
                fut.cancel()
            self.finished.set()  # 取消堵塞全部的 async_q.join()
            self.all_tasks_done.notify_all()  # 取消堵塞全部的 sync_q.join()

    async def wait_closed(self):
        if not self.closing:
            raise RuntimeError("队列已被关闭")
        await asyncio.sleep(0)
        if not self.pending:
            return
        await asyncio.wait(self.pending)

    @property
    def closed(self) -> bool:
        return self.closing and not self.pending

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def sync_q(self) -> "_SyncQueueProxy[T]":
        return self._sync_queue

    @property
    def async_q(self) -> "_AsyncQueueProxy[T]":
        return self._async_queue

    def _init(self):
        self._queue = deque()  # type: Deque[T]

    def qsize(self) -> int:
        return len(self._queue)

    def put(self, item: T):
        self._queue.append(item)

    def get(self) -> T:
        return self._queue.popleft()

    def put_internal(self, item: T):
        self.put(item)
        self.unfinished_tasks += 1
        self.finished.clear()

    def notify_sync_not_empty(self):
        def f():
            with self.sync_mutex:
                self.sync_not_empty.notify()

        self.loop.run_in_executor(None, f)

    def notify_sync_not_full(self):
        def f():
            with self.sync_mutex:
                self.sync_not_full.notify()

        fut = asyncio.ensure_future(self.loop.run_in_executor(None, f))
        fut.add_done_callback(self.pending.discard)
        self.pending.add(fut)

    def notify_async_not_empty(self, *, threadsafe: bool):
        async def f():
            async with self.async_mutex:
                self.async_not_empty.notify()

        def task_maker():
            task = self.loop.create_task(f())
            task.add_done_callback(self.pending.discard)
            self.pending.add(task)

        if threadsafe:
            self._call_soon_threadsafe(task_maker)
        else:
            self._call_soon(task_maker)

    def notify_async_not_full(self, *, threadsafe: bool):
        async def f():
            async with self.async_mutex:
                self.async_not_full.notify()

        def task_maker():
            task = self.loop.create_task(f())
            task.add_done_callback(self.pending.discard)
            self.pending.add(task)

        if threadsafe:
            self._call_soon_threadsafe(task_maker)
        else:
            self._call_soon(task_maker)

    def check_closing(self):
        if self.closing:
            raise RuntimeError("禁止对已关闭的队列进行操作")


# noinspection PyProtectedMember
class _SyncQueueProxy(SyncQueue[T]):  # pylint: disable=W0212
    """同步"""

    def __init__(self, parent: Queue[T]):
        self._parent = parent

    @property
    def maxsize(self) -> int:
        return self._parent.maxsize

    @property
    def closed(self) -> bool:
        return self._parent.closed

    def task_done(self):
        self._parent.check_closing()
        with self._parent.all_tasks_done:
            unfinished = self._parent.unfinished_tasks - 1
            if unfinished <= 0:
                if unfinished < 0:
                    raise ValueError("task_done() 执行次数过多")
                self._parent.all_tasks_done.notify_all()
                self._parent.loop.call_soon_threadsafe(self._parent.finished.set)
            self._parent.unfinished_tasks = unfinished

    def join(self):
        self._parent.check_closing()
        with self._parent.all_tasks_done:
            while self._parent.unfinished_tasks:
                self._parent.all_tasks_done.wait()
                self._parent.check_closing()

    def qsize(self) -> int:
        """返回队列的大致大小（不可靠）"""
        return self._parent.qsize()

    @property
    def unfinished_tasks(self) -> int:
        """返回未完成 task 的数量"""
        return self._parent.unfinished_tasks

    def empty(self) -> bool:
        return not self._parent.qsize()

    def full(self) -> bool:
        return 0 < self._parent.maxsize <= self._parent.qsize()

    def put(self, item: T, block: bool = True, timeout: OptFloat = None):
        self._parent.check_closing()
        with self._parent.sync_not_full:
            if self._parent.maxsize > 0:
                if not block:
                    if self._parent.qsize() >= self._parent.maxsize:
                        raise SyncQueueFull
                elif timeout is None:
                    while self._parent.qsize() >= self._parent.maxsize:
                        self._parent.sync_not_full.wait()
                elif timeout < 0:
                    raise ValueError("'timeout' 必须为一个非负数")
                else:
                    time = self._parent.loop.time
                    end_time = time() + timeout
                    while self._parent.qsize() >= self._parent.maxsize:
                        remaining = end_time - time()
                        if remaining <= 0.0:
                            raise SyncQueueFull
                        self._parent.sync_not_full.wait(remaining)
            self._parent.put_internal(item)
            self._parent.sync_not_empty.notify()
            self._parent.notify_async_not_empty(threadsafe=True)

    def get(self, block: bool = True, timeout: OptFloat = None) -> T:
        self._parent.check_closing()
        with self._parent.sync_not_empty:
            if not block:
                if not self._parent.qsize():
                    raise SyncQueueEmpty
            elif timeout is None:
                while not self._parent.qsize():
                    self._parent.sync_not_empty.wait()
            elif timeout < 0:
                raise ValueError("'timeout' 必须为一个非负数")
            else:
                time = self._parent.loop.time
                end_time = time() + timeout
                while not self._parent.qsize():
                    remaining = end_time - time()
                    if remaining <= 0.0:
                        raise SyncQueueEmpty
                    self._parent.sync_not_empty.wait(remaining)
            item = self._parent.get()
            self._parent.sync_not_full.notify()
            self._parent.notify_async_not_full(threadsafe=True)
            return item

    def put_nowait(self, item: T):
        return self.put(item, block=False)

    def get_nowait(self) -> T:
        return self.get(block=False)


# noinspection PyProtectedMember
class _AsyncQueueProxy(AsyncQueue[T]):  # pylint: disable=W0212
    """异步"""

    def __init__(self, parent: Queue[T]):
        self._parent = parent

    @property
    def closed(self) -> bool:
        return self._parent.closed

    def qsize(self) -> int:
        return self._parent.qsize()

    @property
    def unfinished_tasks(self) -> int:
        return self._parent.unfinished_tasks

    @property
    def maxsize(self) -> int:
        return self._parent.maxsize

    def empty(self) -> bool:
        return self.qsize() == 0

    def full(self) -> bool:
        if self._parent.maxsize <= 0:
            return False
        return self.qsize() >= self._parent.maxsize

    async def put(self, item: T) -> None:
        self._parent.check_closing()
        async with self._parent.async_not_full:
            self._parent.sync_mutex.acquire()
            locked = True
            try:
                if self._parent.maxsize > 0:
                    do_wait = True
                    while do_wait:
                        do_wait = self._parent.qsize() >= self._parent.maxsize
                        if do_wait:
                            locked = False
                            self._parent.sync_mutex.release()
                            await self._parent.async_not_full.wait()
                            self._parent.sync_mutex.acquire()
                            locked = True

                self._parent.put_internal(item)
                self._parent.async_not_empty.notify()
                self._parent.notify_sync_not_empty()
            finally:
                if locked:
                    self._parent.sync_mutex.release()

    def put_nowait(self, item: T):
        self._parent.check_closing()
        with self._parent.sync_mutex and 0 < self._parent.maxsize <= self._parent.qsize():
            raise AsyncQueueFull

        self._parent.put_internal(item)
        self._parent.notify_async_not_empty(threadsafe=False)
        self._parent.notify_sync_not_empty()

    async def get(self) -> T:
        self._parent.check_closing()
        async with self._parent.async_not_empty:
            self._parent.sync_mutex.acquire()
            locked = True
            try:
                do_wait = True
                while do_wait:
                    do_wait = self._parent.qsize() == 0

                    if do_wait:
                        locked = False
                        self._parent.sync_mutex.release()
                        await self._parent.async_not_empty.wait()
                        self._parent.sync_mutex.acquire()
                        locked = True

                item = self._parent.get()
                self._parent.async_not_full.notify()
                self._parent.notify_sync_not_full()
                return item
            finally:
                if locked:
                    self._parent.sync_mutex.release()

    def get_nowait(self) -> T:
        self._parent.check_closing()
        with self._parent.sync_mutex:
            if self._parent.qsize() == 0:
                raise AsyncQueueEmpty

            item = self._parent.get()
            self._parent.notify_async_not_full(threadsafe=False)
            self._parent.notify_sync_not_full()
            return item

    def task_done(self):
        self._parent.check_closing()
        with self._parent.all_tasks_done:
            if self._parent.unfinished_tasks <= 0:
                raise ValueError("task_done() called too many times")
            self._parent.unfinished_tasks -= 1
            if self._parent.unfinished_tasks == 0:
                self._parent.finished.set()
                self._parent.all_tasks_done.notify_all()

    async def join(self) -> None:
        while True:
            with self._parent.sync_mutex:
                self._parent.check_closing()
                if self._parent.unfinished_tasks == 0:
                    break
            await self._parent.finished.wait()


class PriorityQueue(Queue[T]):
    """优先级队列"""

    def _init(self):
        self._heap_queue: List[T] = []

    def qsize(self) -> int:
        return len(self._heap_queue)

    def put(self, item: T):
        if not isinstance(item, tuple):
            if hasattr(item, "priority"):
                item = (int(item.priority), item)
            else:
                try:
                    item = (int(item), item)
                except (TypeError, ValueError):
                    pass
        heappush(self._heap_queue, item)

    def get(self) -> T:
        return heappop(self._heap_queue)


class LifoQueue(Queue[T]):
    """后进先出队列"""

    def qsize(self) -> int:
        return len(self._queue)

    def put(self, item: T):
        self._queue.append(item)

    def get(self) -> T:
        return self._queue.pop()
