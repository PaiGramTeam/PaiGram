from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.template import TemplateService
from modules.apihelper.client.components.calendar import Calendar
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class CalendarPlugin(Plugin, BasePlugin):
    """深渊数据查询"""

    def __init__(
        self,
        template_service: TemplateService = None,
        assets_service: AssetsService = None,
    ):
        self.template_service = template_service
        self.assets_service = assets_service
        self.calendar = Calendar()

    @handler.command("calendar", block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, _: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 查询日历", user.full_name, user.id)
        await message.reply_chat_action(ChatAction.TYPING)
        data = await self.calendar.get_photo_data(self.assets_service)
        image = await self.template_service.render(
            "genshin/calendar/calendar.html",
            data,
            query_selector=".container",
        )
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await image.reply_photo(message)
