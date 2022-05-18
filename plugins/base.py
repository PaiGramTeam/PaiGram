import datetime

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler

from logger import Log
from service import BaseService


class BasePlugins:
    def __init__(self, service: BaseService):
        self.service = service

    @staticmethod
    async def cancel(update: Update, _: CallbackContext) -> int:
        await update.message.reply_text("退出命令")
        return ConversationHandler.END

    @staticmethod
    async def _clean(context: CallbackContext, chat_id: int, message_id: int) -> bool:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except BadRequest as error:
            if "not found" in str(error):
                Log.warning(f"定时删除消息[chat_id→{chat_id}|message_id→{message_id}]失败 消息不存在")
            else:
                Log.warning(f"定时删除消息[chat_id→{chat_id}|message_id→{message_id}]失败 \n", error)
        return False

    def _add_delete_message_job(self, context: CallbackContext, chat_id: int, message_id: int,
                                delete_seconds: int = 60):
        context.job_queue.scheduler.add_job(self._clean, "date",
                                            id=f"{chat_id}|{message_id}|auto_clean_message",
                                            name=f"{chat_id}|{message_id}|auto_clean_message",
                                            args=[context, chat_id, message_id],
                                            run_date=context.job_queue._tz_now() + datetime.timedelta(
                                                seconds=delete_seconds), replace_existing=True)
