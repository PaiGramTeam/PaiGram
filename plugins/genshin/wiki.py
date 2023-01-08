from telegram import Update
from telegram.ext import CallbackContext, CommandHandler

from core.plugin import Plugin, handler
from core.services.wiki.services import WikiService
from utils.decorators.admins import bot_admins_rights_check


class Wiki(Plugin):
    """有关WIKI操作"""

    def __init__(self, wiki_service: WikiService = None):
        self.wiki_service = wiki_service

    @handler(CommandHandler, command="refresh_wiki", block=False)
    @bot_admins_rights_check
    async def refresh_wiki(self, update: Update, _: CallbackContext):
        message = update.effective_message
        await message.reply_text("正在刷新Wiki缓存，请稍等")
        await self.wiki_service.refresh_wiki()
        await message.reply_text("刷新Wiki缓存成功")
