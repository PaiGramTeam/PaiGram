import os
import re
from datetime import datetime, timedelta

from genshin import GenshinException, DataNotPublic
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.template.services import TemplateService
from core.user.error import UserNotFoundError
from core.user.services import UserService
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


def get_now() -> datetime:
    now = datetime.now()
    return (now - timedelta(days=1)) if now.day == 1 and now.hour <= 4 else now


def check_ledger_month(context: CallbackContext) -> int:
    now_time = get_now()
    month = now_time.month
    args = get_all_args(context)
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

    if month in allow_month:
        return month
    elif isinstance(month, int):
        raise IndexError
    return now_time.month


class Ledger(Plugin, BasePlugin):
    """旅行札记"""

    def __init__(
        self,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
        template_service: TemplateService = None,
    ):
        self.template_service = template_service
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.current_dir = os.getcwd()

    async def _start_get_ledger(self, client, month=None) -> bytes:
        try:
            diary_info = await client.get_diary(client.uid, month=month)
        except GenshinException as error:
            raise error
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
            "uid": client.uid,
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
        png_data = await self.template_service.render(
            "genshin/ledger/ledger.html", ledger_data, {"width": 580, "height": 610}
        )
        return png_data

    @handler(CommandHandler, command="ledger", block=False)
    @handler(MessageHandler, filters=filters.Regex("^旅行札记查询(.*)"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        try:
            month = check_ledger_month(context)
        except IndexError:
            reply_message = await message.reply_text("仅可查询最新三月的数据，请重新输入")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 查询旅行札记")
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            client = await get_genshin_client(user.id)
            png_data = await self._start_get_ledger(client, month)
        except (UserNotFoundError, CookiesNotFoundError):
            if filters.ChatType.GROUPS.filter(message):
                buttons = [[InlineKeyboardButton("点我私聊", url=f"https://t.me/{context.bot.username}?start=set_cookie")]]
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号")
            return
        except DataNotPublic:
            reply_message = await message.reply_text("查询失败惹，可能是旅行札记功能被禁用了？")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(png_data, filename=f"{client.uid}.png", allow_sending_without_reply=True)
