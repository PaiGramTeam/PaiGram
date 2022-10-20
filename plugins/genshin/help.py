from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import CommandHandler, CallbackContext

from core.bot import bot
from core.plugin import Plugin, handler
from core.template import TemplateService
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class HelpPlugin(Plugin):
    def __init__(self, template_service: TemplateService = None):
        self.file_id = None
        self.help_png = None
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
        if self.file_id is None or bot.config.debug:
            await message.reply_chat_action(ChatAction.TYPING)
            help_png = await self.template_service.render("bot/help/help.html", {}, {"width": 1280, "height": 900})
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            reply_photo = await message.reply_photo(help_png, filename="help.png", allow_sending_without_reply=True)
            photo = reply_photo.photo[0]
            self.file_id = photo.file_id
        else:
            try:
                await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
                await message.reply_photo(self.file_id, allow_sending_without_reply=True)
            except BadRequest as error:
                self.file_id = None
                logger.error("发送图片失败，尝试清空已经保存的file_id，错误信息为", error)
                await message.reply_text("发送图片失败", allow_sending_without_reply=True)
