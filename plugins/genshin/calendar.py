from datetime import datetime, timedelta
from typing import Dict

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, MessageHandler, filters

from core.base.assets import AssetsService
from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.template import TemplateService
from modules.apihelper.client.components.calendar import Calendar
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib


class CalendarPlugin(Plugin, BasePlugin):
    """活动日历查询"""

    def __init__(
        self,
        template_service: TemplateService = None,
        assets_service: AssetsService = None,
        redis: RedisDB = None,
    ):
        self.template_service = template_service
        self.assets_service = assets_service
        self.calendar = Calendar()
        self.cache = redis.client

    async def _fetch_data(self) -> Dict:
        if data := await self.cache.get("plugin:calendar"):
            return jsonlib.loads(data.decode("utf-8"))
        data = await self.calendar.get_photo_data(self.assets_service)
        now = datetime.now()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await self.cache.set("plugin:calendar", jsonlib.dumps(data, default=lambda x: x.dict()), ex=next_hour - now)
        return data

    @handler.command("calendar", block=False)
    @handler(MessageHandler, filters=filters.Regex(r"^(活动)+(日历|日历列表)$"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, _: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        mode = "list" if "列表" in message.text else "calendar"
        logger.info("用户 %s[%s] 查询日历 | 模式 %s", user.full_name, user.id, mode)
        await message.reply_chat_action(ChatAction.TYPING)
        data = await self._fetch_data()
        data["display_mode"] = mode
        image = await self.template_service.render(
            "genshin/calendar/calendar.html",
            data,
            query_selector=".container",
        )
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await image.reply_photo(message)
