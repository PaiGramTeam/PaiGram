from telegram.ext import CallbackContext, ExtBot

from service import BaseService


class PaimonContext(CallbackContext[ExtBot, dict, dict, dict]):
    """
    PaimoeContext 类
    """

    @property
    def service(self) -> BaseService:
        value = self.bot_data.get("service")
        if value is None:
            raise RuntimeError("没有与此上下文对象关联的实例化服务")
        return value
