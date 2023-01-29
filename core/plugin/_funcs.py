from pathlib import Path
from typing import Optional, Union

import aiofiles
import httpx
from httpx import UnsupportedProtocol
from telegram import Chat, Message, ReplyKeyboardRemove, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, ConversationHandler, Job

from core.builtins.contexts import TGContext, TGUpdate
from core.helpers import get_chat
from core.plugin._handler import conversation, handler
from utils.const import CACHE_DIR, REQUEST_HEADERS
from utils.error import UrlResourcesNotFoundError
from utils.helpers import sha1
from utils.log import logger

__all__ = (
    "PluginFuncs",
    "ConversationFuncs",
)


async def _delete_message(context: CallbackContext) -> None:
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


class PluginFuncs:
    @staticmethod
    def add_delete_message_job(
        delete_seconds: int = 60,
        message: Optional[Union[int, Message]] = None,
        *,
        chat: Optional[Union[int, Chat]] = None,
        context: Optional[CallbackContext] = None,
    ) -> Job:
        """延迟删除消息"""
        update = TGUpdate.get()
        message = message or update.effective_message

        if isinstance(message, Message):
            if chat is None:
                chat = message.chat_id
            message = message.id

        chat = chat.id if isinstance(chat, Chat) else chat

        if context is None:
            context = TGContext.get()

        return context.job_queue.run_once(
            callback=_delete_message,
            when=delete_seconds,
            data=message,
            name=f"{chat}|{message}|delete_message",
            chat_id=chat,
            job_kwargs={"replace_existing": True, "id": f"{chat}|{message}|delete_message"},
        )

    @staticmethod
    async def url_to_file(url: str, return_path: bool = False) -> str:
        url_sha1 = sha1(url)  # url 的 hash 值
        pathed_url = Path(url)

        file_name = url_sha1 + pathed_url.suffix
        file_path = CACHE_DIR.joinpath(file_name)

        if not file_path.exists():  # 若文件不存在，则下载
            async with httpx.AsyncClient(headers=REQUEST_HEADERS) as client:
                try:
                    response = await client.get(url)
                except UnsupportedProtocol:
                    logger.error("链接不支持 url[%s]", url)
                    return ""

                if response.is_error:
                    logger.error("请求出现错误 url[%s] status_code[%s]", url, response.status_code)
                    raise UrlResourcesNotFoundError(url)

                if response.status_code != 200:
                    logger.error("url_to_file 获取url[%s] 错误 status_code[%s]", url, response.status_code)
                    raise UrlResourcesNotFoundError(url)

            async with aiofiles.open(file_path, mode="wb") as f:
                await f.write(response.content)

        logger.debug("url_to_file 获取url[%s] 并下载到 file_dir[%s]", url, file_path)

        return file_path if return_path else Path(file_path).as_uri()


class ConversationFuncs:
    @conversation.fallback
    @handler.command(command="cancel", block=True)
    async def cancel(self, update: Update) -> int:
        await update.effective_message.reply_text("退出命令", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END