

from telegram import Update, ReplyKeyboardRemove
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler

from utils.log import logger


async def clean_message(context: CallbackContext):
    job = context.job
    logger.debug(f"删除消息 chat_id[{job.chat_id}] 的 message_id[{job.data}]")
    try:
        await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data)
    except BadRequest as error:
        if "not found" in str(error):
            logger.warning(f"Auth模块删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败 消息不存在")
        elif "Message can't be deleted" in str(error):
            logger.warning(
                f"Auth模块删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败 消息无法删除 可能是没有授权")
        else:
            logger.error(f"Auth模块删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败", error)


def add_delete_message_job(context: CallbackContext, chat_id: int, message_id: int, delete_seconds: int):
    context.job_queue.run_once(callback=clean_message, when=delete_seconds, data=message_id,
                               name=f"{chat_id}|{message_id}|clean_message", chat_id=chat_id,
                               job_kwargs={"replace_existing": True,
                                           "id": f"{chat_id}|{message_id}|clean_message"})


class BasePlugin:

    @staticmethod
    async def cancel(update: Update, _: CallbackContext) -> int:
        await update.message.reply_text("退出命令", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    @staticmethod
    def _add_delete_message_job(context: CallbackContext, chat_id: int, message_id: int, delete_seconds: int = 60):
        return add_delete_message_job(context, chat_id, message_id, delete_seconds)