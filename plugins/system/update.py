import asyncio
import json
import os
from sys import executable

from aiofiles import open as async_open
from telegram import Update, Message
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, CommandHandler

from core.bot import bot
from core.plugin import handler, Plugin
from utils.bot import get_args
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import execute
from utils.log import logger

current_dir = os.getcwd()

UPDATE_DATA = os.path.join(current_dir, "data", "update.json")


class UpdatePlugin(Plugin):
    def __init__(self):
        self._lock = asyncio.Lock()

    @staticmethod
    async def __async_init__():
        if os.path.exists(UPDATE_DATA):
            async with async_open(UPDATE_DATA) as file:
                data = json.loads(await file.read())
            try:
                reply_text = Message.de_json(data, bot.app.bot)
                await reply_text.edit_text("重启成功")
            except (BadRequest, Forbidden, KeyError) as exc:
                logger.error("UpdatePlugin 编辑消息出现错误")
                logger.exception(exc)
            os.remove(UPDATE_DATA)

    @handler(CommandHandler, command="update", block=False)
    @bot_admins_rights_check
    async def update(self, update: Update, context: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        args = get_args(context)
        logger.info(f"用户 {user.full_name}[{user.id}] update命令请求")
        if self._lock.locked():
            await message.reply_text("程序正在更新 请勿重复操作")
            return
        async with self._lock:
            reply_text = await message.reply_text("正在更新")
            logger.info("正在更新代码")
            await execute("git fetch --all")
            if len(args) > 0:
                await execute("git reset --hard origin/main")
            await execute("git pull --all")
            if len(args) > 0:
                await execute(f"{executable} -m poetry install --extras all")
            logger.info("更新成功 正在重启")
            await reply_text.edit_text("更新成功 正在重启")
            async with async_open(UPDATE_DATA, mode="w", encoding="utf-8") as file:
                await file.write(reply_text.to_json())
        raise SystemExit
