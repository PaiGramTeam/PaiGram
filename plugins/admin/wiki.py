from telegram import Update
from telegram.ext import CallbackContext

from core.plugin import Plugin, handler
from core.services.wiki.services import WikiService


class WikiPlugin(Plugin):
    """有关WIKI操作"""

    def __init__(self, wiki_service: WikiService):
        self.wiki_service = wiki_service

    @handler.command("refresh_wiki", block=False, admin=True)
    async def refresh_wiki(self, update: Update, _: CallbackContext):
        message = update.effective_message
        await message.reply_text("正在刷新Wiki缓存，请稍等")
        await self.wiki_service.refresh_wiki()
        await message.reply_text("刷新Wiki缓存成功")
