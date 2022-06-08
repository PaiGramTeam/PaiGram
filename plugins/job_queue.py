from typing import List

from telegram.ext import CallbackContext

from logger import Log
from plugins.base import BasePlugins
from service import BaseService


class JobQueue(BasePlugins):

    def __init__(self, service: BaseService):
        super().__init__(service)
        self.new_post_id_list_cache: List[int] = []

    async def start_job(self, _: CallbackContext) -> None:
        Log.info("正在检查化必要模块是否正常工作")
        Log.info("正在检查Playwright")
        try:
            # 尝试获取 browser 如果获取失败尝试初始化
            await self.service.template.get_browser()
        except TimeoutError as err:
            Log.error("初始化Playwright超时，请检查日记查看错误 \n", err)
        except AttributeError as err:
            Log.error("初始化Playwright时变量为空，请检查日记查看错误 \n", err)
        else:
            Log.info("检查Playwright成功")
        Log.info("检查完成")

    async def check_cookie(self, _: CallbackContext):
        pass
