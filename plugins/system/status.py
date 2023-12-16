import asyncio
import os
from platform import python_version
from time import time
from typing import TYPE_CHECKING

import psutil
from telegram import __version__

from core.plugin import Plugin, handler
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class Status(Plugin):
    def __init__(self):
        self.pid = os.getpid()
        self.time_form = "%m/%d %H:%M"

    @handler.command(command="status", block=False, admin=True)
    async def send_log(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        logger.info("用户 %s[%s] status 命令请求", user.full_name, user.id)
        message = update.effective_message
        current_process = psutil.Process(self.pid)
        psutil.cpu_percent()
        await asyncio.sleep(0.1)
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        total_memory = memory.total
        used_memory = memory.used
        process_cpu_use = current_process.cpu_percent()
        process_use = current_process.memory_info()
        start_time = current_process.create_time()

        memory_text = (
            f"{total_memory / (1024 * 1024 * 1024):.2f}GB/"
            f"{used_memory / (1024 * 1024 * 1024):.2f}GB/"
            f"{process_use.rss / (1024 * 1024 * 1024):.2f}GB"
        )

        text = (
            "PaiGram 运行状态"
            f"Python 版本: `{python_version()}` \n"
            f"Telegram 版本: `{__version__}` \n"
            f"CPU使用率: `{cpu_percent}%/{process_cpu_use}%` \n"
            f"当前使用的内存: `{memory_text}` \n"
            f"运行时间: `{self.get_bot_uptime(start_time)}` \n"
        )
        await message.reply_markdown_v2(text)

    def get_bot_uptime(self, start_time: float) -> str:
        uptime_sec = time() - start_time
        return self.human_time_duration(int(uptime_sec), self.time_form)

    @staticmethod
    def human_time_duration(seconds: int, time_form: str) -> str:
        parts = {}
        time_units = (
            ("%m", 60 * 60 * 24 * 30),
            ("%d", 60 * 60 * 24),
            ("%H", 60 * 60),
            ("%M", 60),
            ("%S", 1),
        )
        for unit, div in time_units:
            amount, seconds = divmod(int(seconds), div)
            parts[unit] = str(amount)
        for key, value in parts.items():
            time_form = time_form.replace(key, value)
        return time_form
