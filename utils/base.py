from telegram.ext import CallbackContext, ExtBot

from service import BaseService


class PaimonContext(CallbackContext[ExtBot, dict, dict, dict]):
    """
    PaimoeContext 类
    """

    @property
    def service(self) -> BaseService:
        """在回调中从 bot_data 获取 service 实例
        :return: BaseService 实例
        """
        value = self.application.bot_data.get("service")
        if value is None:
            raise RuntimeError("没有找到与此上下文对象关联的实例化服务")
        return value
