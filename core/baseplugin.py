from telegram import ReplyKeyboardRemove, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, ConversationHandler

from core.plugin import conversation, handler
from utils.log import logger


async def clean_message(context: CallbackContext):
    job = context.job
    logger.debug(f"删除消息 chat_id[{job.chat_id}] 的 message_id[{job.data}]")
    try:
        # noinspection PyTypeChecker
        await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data)
    except BadRequest as exc:
        if "not found" in str(exc):
            logger.warning(f"删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败 消息不存在")
        elif "Message can't be deleted" in str(exc):
            logger.warning(f"删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败 消息无法删除 可能是没有授权")
        else:
            logger.error(f"删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败")
            logger.exception(exc)
    except Forbidden as exc:
        if "bot was kicked" in str(exc):
            logger.warning(f"删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败 已经被踢出群")
        else:
            logger.error(f"删除消息 chat_id[{job.chat_id}] message_id[{job.data}]失败")
            logger.exception(exc)


def add_delete_message_job(context: CallbackContext, chat_id: int, message_id: int, delete_seconds: int):
    context.job_queue.run_once(
        callback=clean_message,
        when=delete_seconds,
        data=message_id,
        name=f"{chat_id}|{message_id}|clean_message",
        chat_id=chat_id,
        job_kwargs={"replace_existing": True, "id": f"{chat_id}|{message_id}|clean_message"},
    )


class _BasePlugin:
    @staticmethod
    def _add_delete_message_job(context: CallbackContext, chat_id: int, message_id: int, delete_seconds: int = 60):
        return add_delete_message_job(context, chat_id, message_id, delete_seconds)


class _Conversation(_BasePlugin):
    @conversation.fallback
    @handler.command(command="cancel", block=True)
    async def cancel(self, update: Update, _: CallbackContext) -> int:
        await update.effective_message.reply_text("退出命令", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


class BasePlugin(_BasePlugin):
    Conversation = _Conversation
