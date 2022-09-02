from abc import ABC, abstractmethod


class Service(ABC):
    @abstractmethod
    def __init__(self, *args, **kwargs):
        """初始化"""

    @abstractmethod
    async def start(self, *args, **kwargs):
        """启动 service"""

    @abstractmethod
    async def stop(self, *args, **kwargs):
        """关闭 service"""
