from telegram import Update
from telegram.ext import CallbackContext

from config import config
from logger import Log
from plugins.base import BasePlugins
from service import BaseService


class Help(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)
        self.help_png = None

    async def command_start(self, update: Update, _: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        Log.info(f"用户 {user.full_name}[{user.id}] 帮助命令")
        if self.help_png is None or config.DEBUG:
            self.help_png = await self.service.template.render('bot', "help.html", {}, {"width": 768, "height": 768})
        await message.reply_photo(self.help_png, filename=f"help.png", allow_sending_without_reply=True)
