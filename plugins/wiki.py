from typing import List

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, BaseHandler

from manager import listener_plugins_class
from plugins.admin import bot_admins_only
from plugins.base import BasePlugins
from service import BaseService


@listener_plugins_class()
class Wiki(BasePlugins):
    """
    有关WIKI
    """

    @staticmethod
    def create_handlers(service: BaseService) -> List[BaseHandler]:
        wiki = Wiki(service)
        return [
            CommandHandler("refresh_wiki", wiki.refresh_wiki, block=False),
        ]

    @bot_admins_only
    async def refresh_wiki(self, update: Update, _: CallbackContext):
        message = update.message
        await message.reply_text("正在刷新Wiki缓存，请稍等")
        await self.service.wiki.refresh_wiki()
        await message.reply_text("刷新Wiki缓存成功")
