import json
from datetime import datetime
from os import sep

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from telegram.ext import filters

from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class BirthdayPlugin(Plugin, BasePlugin):
    """生日."""

    def __init__(self):
        """加载数据文件."""
        with open(f"resources{sep}json{sep}birthday.json", "r", encoding="utf8") as f:
            self.birthday_list = json.load(f)

    @handler(CommandHandler, command="birthday", block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        month = datetime.today().strftime("%m")
        day = datetime.today().strftime("%d")
        logger.info(f"用户 {user.full_name}[{user.id}] 查询今日角色生日列表")
        try:
            today_list = self.birthday_list[month][day]
            len_today_list = len(today_list)
            name = ""
            for i in range(len_today_list):
                name = f"{name},{today_list[i]}"
            name = name.replace(",", "", 1)
            reply_message = await update.effective_message.reply_text(f"今天是{name}的生日哦！")
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        except KeyError:
            reply_message = await update.effective_message.reply_text("今天没有人过生日哦！")
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
