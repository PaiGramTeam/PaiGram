import json
import os
import re
from datetime import datetime, timedelta

from genshin import GenshinException, DataNotPublic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, ConversationHandler, filters

from core.cookies.services import CookiesService
from core.template.services import TemplateService
from core.user.repositories import UserNotFoundError
from core.user.services import UserService
from utils.log import logger
from plugins.base import BasePlugins
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.plugins.manager import listener_plugins_class
from utils.service.inject import inject


def check_ledger_month(context: CallbackContext) -> int:
    month = datetime.now().month
    args = get_all_args(context)
    if len(args) >= 1:
        month = args[0]
    elif isinstance(month, int):
        pass
    elif re_data := re.findall(r"\d+", str(month)):
        month = int(re_data[0])
    else:
        num_dict = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        month = sum(num_dict.get(i, 0) for i in str(month))
    # check right
    now_time = datetime.now()
    allow_month = [datetime.now().month]
    last_month = now_time.replace(day=1) - timedelta(days=1)
    allow_month.append(last_month.month)
    last_month = last_month.replace(day=1) - timedelta(days=1)
    allow_month.append(last_month.month)

    if month in allow_month:
        return month
    elif isinstance(month, int):
        raise IndexError
    return now_time.month


@listener_plugins_class()
class Ledger(BasePlugins):
    """旅行札记"""

    COMMAND_RESULT, = range(10200, 10201)

    @inject
    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None,
                 template_service: TemplateService = None):
        self.template_service = template_service
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.current_dir = os.getcwd()

    @classmethod
    def create_handlers(cls):
        ledger = cls()
        return [CommandHandler("ledger", ledger.command_start, block=True),
                MessageHandler(filters.Regex(r"^旅行扎记(.*)"), ledger.command_start, block=True)]

    async def _start_get_ledger(self, client, month=None) -> bytes:
        try:
            diary_info = await client.get_diary(client.uid, month=month)
        except GenshinException as error:
            raise error
        color = ["#73a9c6", "#d56565", "#70b2b4", "#bd9a5a", "#739970", "#7a6da7", "#597ea0"]
        categories = [{"id": i.id,
                       "name": i.name,
                       "color": color[i.id % len(color)],
                       "amount": i.amount,
                       "percentage": i.percentage} for i in diary_info.month_data.categories]
        color = [i["color"] for i in categories]

        def format_amount(amount: int) -> str:
            return f"{round(amount / 10000, 2)}w" if amount >= 10000 else amount

        evaluate = """const { Pie } = G2Plot;
    const data = JSON.parse(`""" + json.dumps(categories) + """`);
    const piePlot = new Pie("chartContainer", {
      renderer: "svg",
      animation: false,
      data: data,
      appendPadding: 10,
      angleField: "amount",
      colorField: "name",
      radius: 1,
      innerRadius: 0.7,
      color: JSON.parse(`""" + json.dumps(color) + """`),
      meta: {},
      label: {
        type: "inner",
        offset: "-50%",
        autoRotate: false,
        style: {
          textAlign: "center",
          fontFamily: "tttgbnumber",
        },
        formatter: ({ percentage }) => {
          return percentage > 2 ? `${percentage}%` : "";
        },
      },
      statistic: {
        title: {
          offsetY: -18,
          content: "总计",
        },
        content: {
          offsetY: -10,
          style: {
            fontFamily: "tttgbnumber",
          },
        },
      },
      legend:false,
    });
    piePlot.render();"""
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
        }
        png_data = await self.template_service.render('genshin/ledger', "ledger.html", ledger_data,
                                                      {"width": 580, "height": 610},
                                                      evaluate=evaluate,
                                                      auto_escape=False)
        return png_data

    @error_callable
    @restricts(return_data=ConversationHandler.END)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.message
        try:
            month = check_ledger_month(context)
        except IndexError:
            reply_message = await message.reply_text("仅可查询最新三月的数据，请重新输入")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 查询原石手扎")
        await update.message.reply_chat_action(ChatAction.TYPING)
        try:
            client = await get_genshin_client(user.id, self.user_service, self.cookies_service)
            png_data = await self._start_get_ledger(client, month)
        except UserNotFoundError:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        except DataNotPublic:
            reply_message = await update.message.reply_text("查询失败惹，可能是旅行札记功能被禁用了？")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await update.message.reply_photo(png_data, filename=f"{client.uid}.png", allow_sending_without_reply=True)
