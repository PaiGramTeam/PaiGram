from typing import ClassVar


class BaseService:
    """服务基类"""

    is_component: ClassVar[bool]
    is_dependence: ClassVar[bool]

    def __init_subclass__(cls, component: bool = False, dependence: bool = False) -> None:
        cls.is_component = component
        cls.is_dependence = dependence

    async def start(self) -> None:
        """启动服务"""

    async def stop(self) -> None:
        """关闭服务"""
