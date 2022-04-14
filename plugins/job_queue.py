from telegram.ext import CallbackContext

from logger import Log
from plugins.base import BasePlugins
from service import BaseService


class JobQueue(BasePlugins):

    def __init__(self, service: BaseService):
        super().__init__(service)

    async def start_job(self, _: CallbackContext) -> None:
        Log.info("初始Job启动成功，正在初始化必要任务")
        Log.info("正在初始化浏览器")
        try:
            await self.service.template.get_browser()
        except TimeoutError as err:
            Log.error("初始化浏览器超时，请检查日记查看错误", err)
        except AttributeError as err:
            Log.error("初始化浏览器时变量为空，请检查日记查看错误", err)
        else:
            Log.info("初始化浏览器成功")
        Log.info("初始化Job成功")
