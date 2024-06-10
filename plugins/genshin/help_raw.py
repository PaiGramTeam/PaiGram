import os
from typing import Optional

import aiofiles
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import CallbackContext

from core.config import config
from core.plugin import Plugin, handler
from utils.log import logger

__all__ = ("HelpRawPlugin",)


class HelpRawPlugin(Plugin):
    def __init__(self):
        self.help_raw: Optional[str] = None

    async def initialize(self):
        file_path = os.path.join(os.getcwd(), "resources", "bot", "help", "help.jinja2")
        async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
            html_content = await f.read()
        soup = BeautifulSoup(html_content, "html.parser")
        commands = []
        command_div = soup.find_all("div", class_="command")
        for div in command_div:
            command_name_div = div.find("div", class_="command-name")
            command_description_div = div.find("div", class_="command-description")
            if command_name_div and command_description_div:
                command_name_div_text = command_name_div.text.strip()
                if command_name_div_text.startswith(r"@{{bot_username}}"):
                    command_name_div_text = command_name_div_text.replace(
                        r"@{{bot_username}}", self.application.telegram.bot.name
                    )
                commands.append(f"{command_name_div_text} - {command_description_div.text.strip()}")
        if commands:
            self.help_raw = "\n".join(commands)

    @handler.command(command="help_raw", block=False)
    async def start(self, update: Update, _: CallbackContext):
        message = update.effective_message
        self.log_user(update, logger.info, "发出 help_raw 命令")

        if self.help_raw is None:
            await self.initialize()
        if self.help_raw is None:
            await message.reply_text(f"出错了呜呜呜~ {config.notice.bot_name}没有找到任何帮助信息")
            return
        await message.reply_text(self.help_raw)
