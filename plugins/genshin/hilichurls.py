from os import sep

from telegram import Message, User
from telegram.ext import CallbackContext, filters

from core.plugin import Plugin, handler
from utils.decorators.restricts import restricts
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

__all__ = ("HilichurlsPlugin",)


class HilichurlsPlugin(Plugin):
    """丘丘语字典."""

    def __init__(self):
        """加载数据文件.数据整理自 https://wiki.biligame.com/ys By @zhxycn."""
        with open(f"resources{sep}json{sep}hilichurls_dictionary.json", "r", encoding="utf8") as f:
            self.hilichurls_dictionary = jsonlib.load(f)

    @restricts()
    @handler.command(command="hilichurls", block=False)
    async def command_start(self, user: User, message: Message, context: CallbackContext) -> None:

        args = self.get_args(context)
        if len(args) >= 1:
            msg = args[0]
        else:
            reply_message = await message.reply_text("请输入要查询的丘丘语。")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        search = str.casefold(msg)  # 忽略大小写以方便查询
        if search not in self.hilichurls_dictionary:
            reply_message = await message.reply_text(f"在丘丘语字典中未找到 {msg}。")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 查询丘丘语字典命令请求 || 参数 {msg}")
        result = self.hilichurls_dictionary[f"{search}"]
        await message.reply_markdown_v2(f"丘丘语: `{search}`\n\n`{result}`")
