from telegram import Update, ReplyKeyboardRemove
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, ConversationHandler

from core.plugin import handler, conversation
from utils.bot import get_chat
from utils.log import logger


async def clean_message(context: CallbackContext):
    job = context.job
    message_id = job.data
    chat_info = f"chat_id[{job.chat_id}]"
    try:
        chat = await get_chat(job.chat_id)
        full_name = chat.full_name
        if full_name:
            chat_info = f"{full_name}[{chat.id}]"
        else:
            chat_info = f"{chat.title}[{chat.id}]"
    except (BadRequest, Forbidden) as exc:
        logger.warning("获取 chat info 失败 %s", exc.message)
    except Exception as exc:
        logger.warning("获取 chat info 消息失败 %s", str(exc))
    logger.debug("删除消息 %s message_id[%s]", chat_info, message_id)
    try:
        # noinspection PyTypeChecker
        await context.bot.delete_message(chat_id=job.chat_id, message_id=message_id)
    except BadRequest as exc:
        if "not found" in exc.message:
            logger.warning("删除消息 %s message_id[%s] 失败 消息不存在", chat_info, message_id)
        elif "Message can't be deleted" in exc.message:
            logger.warning("删除消息 %s message_id[%s] 失败 消息无法删除 可能是没有授权", chat_info, message_id)
        else:
            logger.warning("删除消息 %s message_id[%s] 失败 %s", chat_info, message_id, exc.message)
    except Forbidden as exc:
        if "bot was kicked" in exc.message:
            logger.warning("删除消息 %s message_id[%s] 失败 已经被踢出群", chat_info, message_id)
        else:
            logger.warning("删除消息 %s message_id[%s] 失败 %s", chat_info, message_id, exc.message)


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
