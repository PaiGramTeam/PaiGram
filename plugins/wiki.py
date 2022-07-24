from telegram import Update
from telegram.ext import CommandHandler

from utils.plugins.manager import listener_plugins_class
from plugins.admin import bot_admins_only
from plugins.base import BasePlugins
from utils.base import PaimonContext


@listener_plugins_class()
class Wiki(BasePlugins):
    """
    有关WIKI
    """

    @classmethod
    def create_handlers(cls) -> list:
        wiki = cls()
        return [
            CommandHandler("refresh_wiki", wiki.refresh_wiki, block=False),
        ]

    @bot_admins_only
    async def refresh_wiki(self, update: Update, context: PaimonContext):
        message = update.message
        service = context.service
        await message.reply_text("正在刷新Wiki缓存，请稍等")
        await service.wiki.refresh_wiki()
        await message.reply_text("刷新Wiki缓存成功")
