from datetime import datetime
from typing import Optional, TYPE_CHECKING

from simnet.errors import DataNotPublic
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import ConversationHandler, filters
from telegram.helpers import create_deep_linked_url

from core.plugin import Plugin, handler
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from plugins.tools.genshin import GenshinHelper
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from simnet import GenshinClient
    from telegram import Update
    from telegram.ext import ContextTypes

__all__ = ("DailyNotePlugin",)


class DailyNotePlugin(Plugin):
    """每日便签"""

    def __init__(
        self,
        template: TemplateService,
        helper: GenshinHelper,
    ):
        self.template_service = template
        self.helper = helper

    async def _get_daily_note(self, client: "GenshinClient") -> RenderResult:
        daily_info = await client.get_genshin_notes(client.player_id)

        day = datetime.now().strftime("%m-%d %H:%M") + " 星期" + "一二三四五六日"[datetime.now().weekday()]
        resin_recovery_time = (
            daily_info.resin_recovery_time.strftime("%m-%d %H:%M")
            if daily_info.max_resin - daily_info.current_resin
            else None
        )
        realm_recovery_time = (
            (datetime.now().astimezone() + daily_info.remaining_realm_currency_recovery_time).strftime("%m-%d %H:%M")
            if daily_info.max_realm_currency - daily_info.current_realm_currency
            else None
        )
        remained_time = None
        for i in daily_info.expeditions:
            if remained_time:
                if remained_time < i.remaining_time:
                    remained_time = i.remaining_time
            else:
                remained_time = i.remaining_time
        if remained_time:
            remained_time = (datetime.now().astimezone() + remained_time).strftime("%m-%d %H:%M")

        transformer, transformer_ready, transformer_recovery_time = False, None, None
        if daily_info.remaining_transformer_recovery_time is not None:
            transformer = True
            transformer_ready = daily_info.remaining_transformer_recovery_time.total_seconds() == 0
            transformer_recovery_time = daily_info.transformer_recovery_time.strftime("%m-%d %H:%M")

        render_data = {
            "uid": mask_number(client.player_id),
            "day": day,
            "resin_recovery_time": resin_recovery_time,
            "current_resin": daily_info.current_resin,
            "max_resin": daily_info.max_resin,
            "realm_recovery_time": realm_recovery_time,
            "current_realm_currency": daily_info.current_realm_currency,
            "max_realm_currency": daily_info.max_realm_currency,
            "claimed_commission_reward": daily_info.claimed_commission_reward,
            "completed_commissions": daily_info.completed_commissions,
            "max_commissions": daily_info.max_commissions,
            "expeditions": bool(daily_info.expeditions),
            "remained_time": remained_time,
            "current_expeditions": len(daily_info.expeditions),
            "max_expeditions": daily_info.max_expeditions,
            "remaining_resin_discounts": daily_info.remaining_resin_discounts,
            "max_resin_discounts": daily_info.max_resin_discounts,
            "transformer": transformer,
            "transformer_ready": transformer_ready,
            "transformer_recovery_time": transformer_recovery_time,
        }
        render_result = await self.template_service.render(
            "genshin/daily_note/daily_note.jinja2",
            render_data,
            {"width": 600, "height": 548},
            full_page=False,
            ttl=8 * 60,
        )
        return render_result

    @staticmethod
    def get_task_button(bot_username: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(">> 设置状态提醒 <<", url=create_deep_linked_url(bot_username, "daily_note_tasks"))]]
        )

    @handler.command("dailynote", block=False)
    @handler.message(filters.Regex("^当前状态(.*)"), block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> Optional[int]:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 每日便签命令请求", user.full_name, user.id)

        try:
            # 获取当前用户的 genshin.Client
            async with self.helper.genshin(user.id) as client:
                render_result = await self._get_daily_note(client)
        except DataNotPublic:
            reply_message = await message.reply_text("查询失败惹，可能是便签功能被禁用了？请尝试通过米游社或者 hoyolab 获取一次便签信息后重试。")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return ConversationHandler.END

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(
            message,
            filename=f"{client.player_id}.png",
            allow_sending_without_reply=True,
            reply_markup=self.get_task_button(context.bot.username),
        )
