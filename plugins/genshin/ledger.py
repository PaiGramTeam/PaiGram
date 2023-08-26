import os
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from simnet.errors import DataNotPublic, BadRequest as SimnetBadRequest
from telegram.constants import ChatAction
from telegram.ext import filters

from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from plugins.tools.genshin import GenshinHelper
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from simnet import GenshinClient

__all__ = ("LedgerPlugin",)


class LedgerPlugin(Plugin):
    """旅行札记查询"""

    def __init__(
        self,
        helper: GenshinHelper,
        cookies_service: CookiesService,
        template_service: TemplateService,
    ):
        self.template_service = template_service
        self.cookies_service = cookies_service
        self.current_dir = os.getcwd()
        self.helper = helper

    async def _start_get_ledger(self, client: "GenshinClient", month=None) -> RenderResult:
        diary_info = await client.get_genshin_diary(client.player_id, month=month)
        color = ["#73a9c6", "#d56565", "#70b2b4", "#bd9a5a", "#739970", "#7a6da7", "#597ea0"]
        categories = [
            {
                "id": i.id,
                "name": i.name,
                "color": color[i.id % len(color)],
                "amount": i.amount,
                "percentage": i.percentage,
            }
            for i in diary_info.month_data.categories
        ]
        color = [i["color"] for i in categories]

        def format_amount(amount: int) -> str:
            return f"{round(amount / 10000, 2)}w" if amount >= 10000 else amount

        ledger_data = {
            "uid": mask_number(client.player_id),
            "day": diary_info.month,
            "current_primogems": format_amount(diary_info.month_data.current_primogems),
            "gacha": int(diary_info.month_data.current_primogems / 160),
            "current_mora": format_amount(diary_info.month_data.current_mora),
            "last_primogems": format_amount(diary_info.month_data.last_primogems),
            "last_gacha": int(diary_info.month_data.last_primogems / 160),
            "last_mora": format_amount(diary_info.month_data.last_mora),
            "categories": categories,
            "color": color,
        }
        render_result = await self.template_service.render(
            "genshin/ledger/ledger.jinja2", ledger_data, {"width": 580, "height": 610}
        )
        return render_result

    @handler.command(command="ledger", block=False)
    @handler.message(filters=filters.Regex("^旅行札记查询(.*)"), block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user = update.effective_user
        message = update.effective_message

        now = datetime.now()
        now_time = (now - timedelta(days=1)) if now.day == 1 and now.hour <= 4 else now
        month = now_time.month
        try:
            args = self.get_args(context)
            if len(args) >= 1:
                month = args[0].replace("月", "")
            if re_data := re.findall(r"\d+", str(month)):
                month = int(re_data[0])
            else:
                num_dict = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                month = sum(num_dict.get(i, 0) for i in str(month))
            # check right
            allow_month = [now_time.month]

            last_month = now_time.replace(day=1) - timedelta(days=1)
            allow_month.append(last_month.month)

            last_month = last_month.replace(day=1) - timedelta(days=1)
            allow_month.append(last_month.month)

            if month not in allow_month and isinstance(month, int):
                raise IndexError
            month = now_time.month
        except IndexError:
            reply_message = await message.reply_text("仅可查询最新三月的数据，请重新输入")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return
        logger.info("用户 %s[%s] 查询旅行札记", user.full_name, user.id)
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            async with self.helper.genshin(user.id) as client:
                render_result = await self._start_get_ledger(client, month)
        except DataNotPublic:
            reply_message = await message.reply_text("查询失败惹，可能是旅行札记功能被禁用了？请先通过米游社或者 hoyolab 获取一次旅行札记后重试。")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return
        except SimnetBadRequest as exc:
            if exc.ret_code == -120:
                await message.reply_text("当前角色冒险等阶不足，暂时无法获取信息")
                return
            raise exc
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename=f"{client.player_id}.png", allow_sending_without_reply=True)
