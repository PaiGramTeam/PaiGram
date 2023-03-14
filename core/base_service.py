from abc import ABC
from itertools import chain
from typing import ClassVar, Iterable, Type, TypeVar

from typing_extensions import Self

from utils.helpers import isabstract

__all__ = ("BaseService", "BaseServiceType", "DependenceType", "ComponentType", "get_all_services")


class _BaseService:
    """服务基类"""

    _is_component: ClassVar[bool] = False
    _is_dependence: ClassVar[bool] = False

    def __init_subclass__(cls, load: bool = True, **kwargs):
        cls.is_dependence = cls._is_dependence
        cls.is_component = cls._is_component
        cls.load = load

    async def __aenter__(self) -> Self:
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    async def initialize(self) -> None:
        """Initialize resources used by this service"""

    async def shutdown(self) -> None:
        """Stop & clear resources used by this service"""


class _Dependence(_BaseService, ABC):
    _is_dependence: ClassVar[bool] = True


class _Component(_BaseService, ABC):
    _is_component: ClassVar[bool] = True


class BaseService(_BaseService, ABC):
    Dependence: Type[_BaseService] = _Dependence
    Component: Type[_BaseService] = _Component


BaseServiceType = TypeVar("BaseServiceType", bound=_BaseService)
DependenceType = TypeVar("DependenceType", bound=_Dependence)
ComponentType = TypeVar("ComponentType", bound=_Component)


# noinspection PyProtectedMember
def get_all_services() -> Iterable[Type[_BaseService]]:
    return filter(
        lambda x: x.__name__[0] != "_" and x.load and not isabstract(x),
        chain(BaseService.__subclasses__(), _Dependence.__subclasses__(), _Component.__subclasses__()),
    )
