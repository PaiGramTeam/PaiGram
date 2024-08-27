from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

from simnet.errors import DataNotPublic
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import ConversationHandler, filters
from telegram.helpers import create_deep_linked_url

from core.plugin import Plugin, handler
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from gram_core.plugin.methods.inline_use_data import IInlineUseData
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

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days:
            return f"{days} 天 {hours} 时"
        return f"{hours} 时" if hours else f"{minutes} 分"

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

        daily_task, attendance_countdown = daily_info.daily_task, ""
        if daily_info.daily_task.attendance_visible:
            attendance_countdown = self._format_seconds(
                int(daily_task.stored_attendance_refresh_countdown.total_seconds())
            )

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
            "daily_task": daily_info.daily_task,
            "attendance_countdown": attendance_countdown,
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
            {"width": 600, "height": 645},
            full_page=False,
            ttl=8 * 60,
        )
        return render_result

    @staticmethod
    def get_task_button(bot_username: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(">> 设置状态提醒 <<", url=create_deep_linked_url(bot_username, "daily_note_tasks"))]]
        )

    @handler.command("dailynote", cookie=True, block=False)
    @handler.message(filters.Regex("^当前状态(.*)"), cookie=True, block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> Optional[int]:
        message = update.effective_message
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        self.log_user(update, logger.info, "每日便签命令请求")

        try:
            # 获取当前用户的 genshin.Client
            async with self.helper.genshin(user_id, player_id=uid, offset=offset) as client:
                render_result = await self._get_daily_note(client)
        except DataNotPublic:
            reply_message = await message.reply_text(
                "查询失败惹，可能是便签功能被禁用了？请尝试通过米游社或者 hoyolab 获取一次便签信息后重试。"
            )
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return ConversationHandler.END

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(
            message,
            filename=f"{client.player_id}.png",
            reply_markup=self.get_task_button(context.bot.username),
        )

    async def daily_note_use_by_inline(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        callback_query = update.callback_query
        user = update.effective_user
        user_id = user.id
        uid = IInlineUseData.get_uid_from_context(context)
        self.log_user(update, logger.info, "每日便签命令请求")

        try:
            async with self.helper.genshin(user_id, player_id=uid) as client:
                render_result = await self._get_daily_note(client)
        except DataNotPublic:
            await callback_query.answer(
                "查询失败惹，可能是便签功能被禁用了？请尝试通过米游社或者 hoyolab 获取一次便签信息后重试。",
                show_alert=True,
            )
            return ConversationHandler.END

        await render_result.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        return [
            IInlineUseData(
                text="当前状态",
                hash="dailynote",
                callback=self.daily_note_use_by_inline,
                cookie=True,
                player=True,
            )
        ]
