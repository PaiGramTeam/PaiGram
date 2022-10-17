import os

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, CallbackContext

from core.plugin import Plugin, handler
from utils.decorators.admins import bot_admins_rights_check
from utils.log import logger

current_dir = os.getcwd()
error_log = os.path.join(current_dir, "logs", "error", "error.log")
debug_log = os.path.join(current_dir, "logs", "debug", "debug.log")


class Log(Plugin):
    @handler(CommandHandler, command="send_log", block=False)
    @bot_admins_rights_check
    async def send_log(self, update: Update, _: CallbackContext):
        user = update.effective_user
        logger.info(f"用户 {user.full_name}[{user.id}] send_log 命令请求")
        message = update.effective_message
        if os.path.exists(error_log) and os.path.getsize(error_log) > 0:
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(open(error_log, mode="rb+"), caption="Error Log")
        else:
            await message.reply_text("错误日记未找到")
        if os.path.exists(debug_log) and os.path.getsize(debug_log) > 0:
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(open(debug_log, mode="rb+"), caption="Debug Log")
        else:
            await message.reply_text("调试日记未找到")
