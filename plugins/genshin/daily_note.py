import datetime
from datetime import datetime
from typing import Optional

import genshin
from genshin import DataNotPublic
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message, User
from telegram.constants import ChatAction
from telegram.ext import ConversationHandler, filters
from telegram.helpers import create_deep_linked_url

from core.plugin import Plugin, handler
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from plugins.tools.genshin import GenshinHelper
from utils.decorators.restricts import restricts
from utils.log import logger

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

    async def _get_daily_note(self, client: genshin.Client) -> RenderResult:
        daily_info = await client.get_genshin_notes(client.uid)

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
            "uid": client.uid,
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
            "genshin/daily_note/daily_note.html",
            render_data,
            {"width": 600, "height": 548},
            full_page=False,
            ttl=8 * 60,
        )
        return render_result

    # noinspection SpellCheckingInspection
    @restricts(30)
    @handler.command(command="dailynote", block=False)
    @handler.message(filters=filters.Regex("^当前状态(.*)"), block=False)
    async def command_start(self, user: User, message: Message, bot: Bot) -> Optional[int]:
        logger.info("用户 %s[%s] 每日便签命令请求", user.full_name, user.id)

        try:
            # 获取当前用户的 genshin.Client
            client = await self.helper.get_genshin_client(user.id)
            if client is None:
                buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(bot.username, "set_cookie"))]]
                if filters.ChatType.GROUPS.filter(message):
                    reply_message = await message.reply_text(
                        "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                    )
                    self.add_delete_message_job(reply_message, delay=30)
                    self.add_delete_message_job(message, delay=30)
                else:
                    await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
                return
            # 渲染
            render_result = await self._get_daily_note(client)
        except DataNotPublic:
            reply_message = await message.reply_text("查询失败惹，可能是便签功能被禁用了？请尝试通过米游社或者 hoyolab 获取一次便签信息后重试。")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return ConversationHandler.END

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename=f"{client.uid}.png", allow_sending_without_reply=True)
