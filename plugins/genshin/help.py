from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, CallbackContext

from core.plugin import Plugin, handler
from core.template import TemplateService
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class HelpPlugin(Plugin):
    def __init__(self, template_service: TemplateService = None):
        if template_service is None:
            raise ModuleNotFoundError
        self.template_service = template_service

    @handler(CommandHandler, command="help", block=False)
    @error_callable
    @restricts()
    async def start(self, update: Update, _: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 发出help命令")
        await message.reply_chat_action(ChatAction.TYPING)
        render_result = await self.template_service.render(
            "bot/help/help.html", {}, {"width": 1280, "height": 900}, ttl=30 * 24 * 60 * 60
        )
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename="help.png", allow_sending_without_reply=True)
