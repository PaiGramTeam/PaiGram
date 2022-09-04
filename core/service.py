from abc import ABC, abstractmethod

__all__ = ['Service', 'init_service']

from typing import Callable

from loguru import logger


class Service(ABC):
    @abstractmethod
    def __init__(self, *args, **kwargs):
        """初始化"""

    async def start(self, *args, **kwargs):
        """启动 service"""

    async def stop(self, *args, **kwargs):
        """关闭 service"""


def init_service(func: Callable):
    from core.bot import bot

    try:
        service = bot.init_inject(func)
        logger.success(f'服务 "{service.__class__.__name__}" 初始化成功')
        bot.add_service(service)
    except Exception as e:
        # noinspection PyUnresolvedReferences
        logger.error(f'来自{func.__module__}的服务初始化失败：{e}')
