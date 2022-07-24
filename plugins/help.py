from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import CommandHandler

from config import config
from logger import Log
from utils.plugins.manager import listener_plugins_class
from plugins.base import restricts
from utils.base import PaimonContext


@listener_plugins_class()
class Help:
    """
    帮助
    """

    def __init__(self):
        self.help_png = None
        self.file_id = None

    @classmethod
    def create_handlers(cls) -> list:
        _help = cls()
        return [
            CommandHandler("help", _help.command_start, block=False),
        ]

    @restricts()
    async def command_start(self, update: Update, context: PaimonContext) -> None:
        message = update.message
        user = update.effective_user
        service = context.service
        Log.info(f"用户 {user.full_name}[{user.id}] 发出help命令")
        if self.file_id is None or config.DEBUG:
            await message.reply_chat_action(ChatAction.TYPING)
            help_png = await service.template.render('bot/help', "help.html", {}, {"width": 768, "height": 768})
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
                Log.error("发送图片失败，尝试清空已经保存的file_id，错误信息为", error)
                await message.reply_text("发送图片失败", allow_sending_without_reply=True)
