from abc import ABC, abstractmethod

__all__ = ['Service']


class Service(ABC):
    @abstractmethod
    def __init__(self, *args, **kwargs):
        """初始化"""

    async def start(self, *args, **kwargs):
        """启动 service"""

    async def stop(self, *args, **kwargs):
        """关闭 service"""
