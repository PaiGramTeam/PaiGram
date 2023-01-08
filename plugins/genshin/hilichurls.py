from os import sep

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, filters

from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from utils.bot import get_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


class HilichurlsPlugin(Plugin, BasePlugin):
    """丘丘语字典."""

    def __init__(self):
        """加载数据文件.数据整理自 https://wiki.biligame.com/ys By @zhxycn."""
        with open(f"resources{sep}json{sep}hilichurls_dictionary.json", "r", encoding="utf8") as f:
            self.hilichurls_dictionary = jsonlib.load(f)

    @handler(CommandHandler, command="hilichurls", block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = get_args(context)
        if len(args) >= 1:
            msg = args[0]
        else:
            reply_message = await message.reply_text("请输入要查询的丘丘语。")
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        search = str.casefold(msg)  # 忽略大小写以方便查询
        if search not in self.hilichurls_dictionary:
            reply_message = await message.reply_text(f"在丘丘语字典中未找到 {msg}。")
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 查询丘丘语字典命令请求 || 参数 {msg}")
        result = self.hilichurls_dictionary[f"{search}"]
        await message.reply_markdown_v2(f"丘丘语: `{search}`\n\n`{result}`")
