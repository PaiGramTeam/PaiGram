import asyncio
import datetime

from telegram import Update
from telegram.ext import CallbackContext

from core.plugin import handler, Plugin, job
from core.services.search.services import SearchServices
from utils.log import logger

__all__ = ("SearchPlugin",)


class SearchPlugin(Plugin):
    def __init__(self, search: SearchServices = None):
        self.search = search
        self.lock = asyncio.Lock()

    async def initialize(self):
        async def load_data():
            logger.info("Search 插件模块正在加载搜索条目")
            async with self._lock:
                await self.search.load_data()
            logger.success("Search 插件加载模块搜索条目成功")

        asyncio.create_task(load_data())

    @job.run_repeating(interval=datetime.timedelta(hours=1), name="SaveEntryJob")
    async def save_entry_job(self, _: CallbackContext):
        if self.lock.locked():
            logger.warning("条目数据正在保存 跳过本次定时任务")
        else:
            async with self.lock:
                logger.info("条目数据正在自动保存")
                await self.search.save_entry()
                logger.success("条目数据自动保存成功")

    @handler.command("save_entry", block=False, admin=True)
    async def save_entry(self, update: Update, _: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 保存条目数据命令请求", user.full_name, user.id)
        if self.lock.locked():
            await message.reply_text("条目数据正在保存 请稍后重试")
        else:
            async with self.lock:
                reply_text = await message.reply_text("正在保存数据")
                await self.search.save_entry()
                await reply_text.edit_text("数据保存成功")

    @handler.command("remove_all_entry", block=False)
    async def remove_all_entry(self, update: Update, _: CallbackContext, admin=True):
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 删除全部条目数据命令请求", user.full_name, user.id)
        reply_text = await message.reply_text("正在删除全部条目数据")
        await self.search.remove_all_entry()
        await reply_text.edit_text("删除全部条目数据成功")
