from datetime import datetime, timedelta
from functools import partial
from typing import Dict, List, Optional, TYPE_CHECKING

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, MessageHandler, filters

from core.dependence.assets import AssetsService
from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.template.services import TemplateService
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from modules.apihelper.client.components.calendar import Calendar
from utils.log import logger

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

if TYPE_CHECKING:
    from telegram.ext import ContextTypes
    from gram_core.services.template.models import RenderResult


class CalendarPlugin(Plugin):
    """活动日历查询"""

    def __init__(
        self,
        template_service: TemplateService,
        assets_service: AssetsService,
        redis: RedisDB,
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

    async def render(self, list_mode: bool) -> "RenderResult":
        data = await self._fetch_data()
        data["display_mode"] = "list" if list_mode else "calendar"
        return await self.template_service.render(
            "genshin/calendar/calendar.jinja2",
            data,
            query_selector=".container",
        )

    @handler.command("calendar", block=False)
    @handler(MessageHandler, filters=filters.Regex(r"^(活动)+(日历|日历列表)$"), block=False)
    async def command_start(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        mode = "list" if "列表" in message.text else "calendar"
        self.log_user(update, logger.info, "查询日历 | 模式 %s", mode)
        await message.reply_chat_action(ChatAction.TYPING)
        image = await self.render(mode == "list")
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await image.reply_photo(message)

    async def calendar_use_by_inline(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE", list_mode: bool):
        callback_query = update.callback_query

        self.log_user(update, logger.info, "查询日历 | 列表模式 %s", list_mode)
        await callback_query.answer("正在查询日历，请耐心等待")
        image = await self.render(list_mode)
        await image.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        return [
            IInlineUseData(
                text="活动日历",
                hash="calendar",
                callback=partial(self.calendar_use_by_inline, list_mode=False),
            ),
            IInlineUseData(
                text="活动日历列表",
                hash="calendar_list",
                callback=partial(self.calendar_use_by_inline, list_mode=True),
            ),
        ]
