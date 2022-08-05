from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from apps.wiki.services import WikiService
from plugins.base import BasePlugins
from utils.apps.inject import inject
from utils.decorators.admins import bot_admins_rights_check
from utils.decorators.error import error_callable
from utils.plugins.manager import listener_plugins_class


@listener_plugins_class()
class Wiki(BasePlugins):
    """有关WIKI操作"""

    @inject
    def __init__(self, wiki_service: WikiService):
        self.wiki_service = wiki_service

    @classmethod
    def create_handlers(cls) -> list:
        wiki = cls()
        return [
            CommandHandler("refresh_wiki", wiki.refresh_wiki, block=False),
        ]

    @bot_admins_rights_check
    @error_callable
    async def refresh_wiki(self, update: Update, _: CallbackContext):
        message = update.message
        await message.reply_text("正在刷新Wiki缓存，请稍等")
        await self.wiki_service.refresh_wiki()
        await message.reply_text("刷新Wiki缓存成功")
