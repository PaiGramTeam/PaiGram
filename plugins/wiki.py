from telegram import Update
from telegram.ext import CallbackContext

from plugins.admin import bot_admins_only
from plugins.base import BasePlugins


class Wiki(BasePlugins):
    """
    有关WIKI
    """
    @bot_admins_only
    async def refresh_wiki(self, update: Update, _: CallbackContext):
        message = update.message
        await message.reply_text("正在刷新Wiki缓存，请稍等")
        await self.service.wiki.refresh_wiki()
        await message.reply_text("刷新Wiki缓存成功")
