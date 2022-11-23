import os

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, CallbackContext

from core.config import config
from core.plugin import Plugin, handler
from modules.errorpush import PbClient, PbClientException
from utils.decorators.admins import bot_admins_rights_check
from utils.log import logger

current_dir = os.getcwd()
error_log = os.path.join(current_dir, "logs", "error", "error.log")
debug_log = os.path.join(current_dir, "logs", "debug", "debug.log")


class Log(Plugin):
    def __init__(self):
        self.pb_client = PbClient(config.error.pb_url, 3600, 10000)

    async def send_to_pb(self, file_name: str):
        pb_url = ""
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                pb_url = await self.pb_client.create_pb(f.read())
        except PbClientException as exc:
            logger.warning("上传错误信息至 fars 失败", exc_info=exc)
        except Exception as exc:
            logger.error("上传错误信息至 fars 失败")
            logger.exception(exc)
        return pb_url

    @handler(CommandHandler, command="send_log", block=False)
    @bot_admins_rights_check
    async def send_log(self, update: Update, _: CallbackContext):
        user = update.effective_user
        logger.info(f"用户 {user.full_name}[{user.id}] send_log 命令请求")
        message = update.effective_message
        if os.path.exists(error_log) and os.path.getsize(error_log) > 0:
            pb_url = await self.send_to_pb(error_log)
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(
                open(error_log, mode="rb+"), caption=f"Error Log\n{pb_url}/text" if pb_url else "Error Log"
            )
        else:
            await message.reply_text("错误日记未找到")
        if os.path.exists(debug_log) and os.path.getsize(debug_log) > 0:
            pb_url = await self.send_to_pb(debug_log)
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(
                open(debug_log, mode="rb+"), caption=f"Debug Log\n{pb_url}/text" if pb_url else "Debug Log"
            )
        else:
            await message.reply_text("调试日记未找到")
