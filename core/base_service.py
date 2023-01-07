from typing import ClassVar, List, Self, Type, TypeVar

__all__ = ("BaseService", "BaseServiceType", "DependenceType", "ComponentType", "get_all_service_types")


class _BaseService:
    """服务基类"""

    _is_component: ClassVar[bool] = False
    _is_dependence: ClassVar[bool] = False

    @property
    def is_component(self) -> bool:
        return self._is_component

    @property
    def is_dependence(self) -> bool:
        return self._is_dependence

    async def __aenter__(self) -> Self:
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    async def initialize(self) -> None:
        """Initialize resources used by this service"""

    async def shutdown(self) -> None:
        """Stop & clear resources used by this service"""


class _Dependence(_BaseService):
    _is_dependence: ClassVar[bool] = True


class _Component(_BaseService):
    _is_component: ClassVar[bool] = True


class BaseService(_BaseService):
    Dependence: Type[_BaseService] = _Dependence
    Component: Type[_BaseService] = _Component


BaseServiceType = TypeVar("BaseServiceType", bound=_BaseService)
DependenceType = TypeVar("DependenceType", bound=_Dependence)
ComponentType = TypeVar("ComponentType", bound=_Component)


def get_all_service_types() -> List[Type[_BaseService]]:
    return _BaseService.__subclasses__()
