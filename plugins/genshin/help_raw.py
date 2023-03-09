import os
from typing import Optional

import aiofiles
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import CallbackContext

from core.plugin import Plugin, handler
from utils.log import logger

__all__ = ("HelpRawPlugin",)


class HelpRawPlugin(Plugin):
    def __init__(self):
        self.help_raw: Optional[str] = None

    async def initialize(self):
        file_path = os.path.join(os.getcwd(), "resources", "bot", "help", "help.html")  # resources/bot/help/help.html
        async with aiofiles.open(file_path, mode="r", encoding='utf-8') as f:
            html_content = await f.read()
        soup = BeautifulSoup(html_content, "lxml")
        command_div = soup.find_all("div", _class="command")
        for div in command_div:
            command_name_div = div.find("div", _class="command_name")
            if command_name_div:
                command_description_div = div.find("div", _class="command-description")
                if command_description_div:
                    self.help_raw += f"/{command_name_div.text} - {command_description_div}"

    @handler.command(command="help_raw", block=False)
    async def start(self, update: Update, _: CallbackContext):
        if self.help_raw is not None:
            message = update.effective_message
            user = update.effective_user
            logger.info("用户 %s[%s] 发出 help_raw 命令", user.full_name, user.id)
            await message.reply_text(self.help_raw, allow_sending_without_reply=True)
