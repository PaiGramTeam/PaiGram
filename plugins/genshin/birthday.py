from datetime import datetime

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from telegram.ext import filters

from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from metadata.genshin import AVATAR_DATA
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class BirthdayPlugin(Plugin, BasePlugin):
    """生日."""

    def __init__(self):
        """加载数据文件."""
        self.birthday_list = {}
        for value in AVATAR_DATA.values():
            key = "_".join([str(i) for i in value["birthday"]])
            data = self.birthday_list.get(key, [])
            data.append(value["name"])
            self.birthday_list.update({key: data})

    @handler(CommandHandler, command="birthday", block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        key = datetime.now().strftime("%m_%d")
        logger.info(f"用户 {user.full_name}[{user.id}] 查询今日角色生日列表")

        today_list = self.birthday_list.get(key, [])
        breakpoint()
        text = f"今天是 {'、'.join(today_list)} 的生日哦~" if today_list else "今天没有角色过生日哦~"
        reply_message = await update.effective_message.reply_text(text)
        if filters.ChatType.GROUPS.filter(reply_message):
            self._add_delete_message_job(context, message.chat_id, message.message_id)
            self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
