from multiprocessing import RLock as Lock
from typing import ClassVar, Generic, Optional, TYPE_CHECKING, Type, TypeVar

from typing_extensions import Self

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock as LockType

__all__ = ["singleton", "Singleton"]

T = TypeVar("T")


class _Singleton(Generic[T]):
    lock: ClassVar["LockType"] = Lock()

    __slots__ = "cls", "instance"

    cls: Type[T]
    instance: Optional[T]

    def __init__(self, cls: Type[T]):
        self.cls = cls
        self.instance = None

    def __call__(self, *args, **kwargs) -> T:
        with self.lock:
            if self.instance is None or args or kwargs:
                self.instance = self.cls(*args, **kwargs)
        return self.instance


def singleton(cls: Optional[Type[T]] = None) -> Type[T]:
    """单例装饰器。用于装饰 class , 使之成为单例"""

    def wrap(_cls: Type[T]) -> _Singleton[T]:
        return _Singleton(_cls)

    return wrap if cls is None else wrap(cls)


class Singleton:
    """单例"""

    _lock: ClassVar["LockType"] = Lock()
    _instance: ClassVar[Optional[Self]] = None

    def __new__(cls: Type[T], *args, **kwargs) -> T:
        with cls._lock:
            if cls._instance is None:
                cls._instance = object.__new__(cls)
        return cls._instance
