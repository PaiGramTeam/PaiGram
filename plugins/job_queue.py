import asyncio
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
        Log.info("初始Job启动成功，正在初始化必要任务")
        Log.info("正在初始化浏览器")
        try:
            await self.service.template.get_browser()
        except TimeoutError as err:
            Log.error("初始化浏览器超时，请检查日记查看错误 \n", err)
        except AttributeError as err:
            Log.error("初始化浏览器时变量为空，请检查日记查看错误 \n", err)
        else:
            Log.info("初始化浏览器成功")
        Log.info("初始化Job成功")

    async def post_job(self, _: CallbackContext) -> None:
        while True:
            new_post_id_list_cache: List[int] = []
            new_list = await self.mihoyo.get_new_list(2, 2)
            if new_list.code == 0:
                for post in new_list.data["list"]:
                    post_id = post["post"]["post_id"]
                    new_post_id_list_cache.append(post_id)
            new_list = await self.mihoyo.get_new_list(2, 3)
            if new_list.code == 0:
                for post in new_list.data["list"]:
                    post_id = post["post"]["post_id"]
                    new_post_id_list_cache.append(post_id)
            if len(self.new_post_id_list_cache) == 0:
                return

            await asyncio.sleep(60)
