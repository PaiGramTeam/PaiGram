from typing import List, Optional, TYPE_CHECKING

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, filters

from core.plugin import Plugin, handler
from core.services.template.services import TemplateService
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from utils.log import logger

__all__ = ("HelpPlugin",)

if TYPE_CHECKING:
    from gram_core.services.template.models import RenderResult


class HelpPlugin(Plugin):
    def __init__(self, template_service: TemplateService = None):
        if template_service is None:
            raise ModuleNotFoundError
        self.template_service = template_service

    async def get_help_render(self) -> "RenderResult":
        return await self.template_service.render(
            "bot/help/help.jinja2",
            {"bot_username": self.application.bot.username},
            {"width": 1280, "height": 900},
            ttl=30 * 24 * 60 * 60,
        )

    @handler.command(command="help", block=False)
    @handler.command(command="start", filters=filters.Regex("inline_message$"), block=False)
    async def start(self, update: Update, _: CallbackContext):
        message = update.effective_message
        self.log_user(update, logger.info, "发出help命令")
        await message.reply_chat_action(ChatAction.TYPING)
        render_result = await self.get_help_render()
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename="help.png")

    async def start_use_by_inline(self, update: Update, _: CallbackContext):
        callback_query = update.callback_query
        self.log_user(update, logger.info, "发出help命令")
        render_result = await self.get_help_render()
        await render_result.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        return [
            IInlineUseData(
                text="帮助",
                hash="help",
                callback=self.start_use_by_inline,
            )
        ]
