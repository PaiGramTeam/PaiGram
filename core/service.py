from abc import ABC, abstractmethod
from typing import Callable

from utils.log import logger

__all__ = ["Service", "init_service"]


class Service(ABC):
    @abstractmethod
    def __init__(self, *args, **kwargs):
        """初始化"""

    async def start(self):
        """启动 service"""

    async def stop(self):
        """关闭 service"""


def init_service(func: Callable):
    from core.bot import bot

    if bot.is_running:
        try:
            service = bot.init_inject(func)
            logger.success(f'服务 "{service.__class__.__name__}" 初始化成功')
            bot.add_service(service)
        except Exception as e:  # pylint: disable=W0703
            logger.exception(f"来自{func.__module__}的服务初始化失败：{e}")
    return func
