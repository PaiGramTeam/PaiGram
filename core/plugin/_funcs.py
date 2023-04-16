from pathlib import Path
from typing import List, Optional, Union, TYPE_CHECKING

import aiofiles
import httpx
from httpx import UnsupportedProtocol
from telegram import Chat, Message, ReplyKeyboardRemove, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, ConversationHandler, Job

from core.dependence.redisdb import RedisDB
from core.plugin._handler import conversation, handler
from utils.const import CACHE_DIR, REQUEST_HEADERS
from utils.error import UrlResourcesNotFoundError
from utils.helpers import sha1
from utils.log import logger

if TYPE_CHECKING:
    from core.application import Application

try:
    import ujson as json
except ImportError:
    import json

__all__ = (
    "PluginFuncs",
    "ConversationFuncs",
)


class PluginFuncs:
    _application: "Optional[Application]" = None

    def set_application(self, application: "Application") -> None:
        self._application = application

    @property
    def application(self) -> "Application":
        if self._application is None:
            raise RuntimeError("No application was set for this PluginManager.")
        return self._application

    async def _delete_message(self, context: CallbackContext) -> None:
        job = context.job
        message_id = job.data
        chat_info = f"chat_id[{job.chat_id}]"

        try:
            chat = await self.get_chat(job.chat_id)
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
            logger.warning("删除消息 %s message_id[%s] 失败 %s", chat_info, message_id, exc.message)
        except Forbidden as exc:
            logger.warning("删除消息 %s message_id[%s] 失败 %s", chat_info, message_id, exc.message)
        except Exception as exc:
            logger.error("删除消息 %s message_id[%s] 失败 %s", chat_info, message_id, exc_info=exc)

    async def get_chat(self, chat_id: Union[str, int], redis_db: Optional[RedisDB] = None, expire: int = 86400) -> Chat:
        application = self.application
        redis_db: RedisDB = redis_db or self.application.managers.dependency_map.get(RedisDB, None)

        if not redis_db:
            return await application.bot.get_chat(chat_id)

        qname = f"bot:chat:{chat_id}"

        data = await redis_db.client.get(qname)
        if data:
            json_data = json.loads(data)
            return Chat.de_json(json_data, application.telegram.bot)

        chat_info = await application.telegram.bot.get_chat(chat_id)
        await redis_db.client.set(qname, chat_info.to_json(), ex=expire)
        return chat_info

    def add_delete_message_job(
        self,
        message: Optional[Union[int, Message]] = None,
        *,
        delay: int = 60,
        name: Optional[str] = None,
        chat: Optional[Union[int, Chat]] = None,
        context: Optional[CallbackContext] = None,
    ) -> Job:
        """延迟删除消息"""

        if isinstance(message, Message):
            if chat is None:
                chat = message.chat_id
            message = message.id

        chat = chat.id if isinstance(chat, Chat) else chat

        job_queue = self.application.job_queue or context.job_queue

        if job_queue is None or chat is None:
            raise RuntimeError

        return job_queue.run_once(
            callback=self._delete_message,
            when=delay,
            data=message,
            name=f"{chat}|{message}|{name}|delete_message" if name else f"{chat}|{message}|delete_message",
            chat_id=chat,
            job_kwargs={"replace_existing": True, "id": f"{chat}|{message}|delete_message"},
        )

    @staticmethod
    async def download_resource(url: str, return_path: bool = False) -> str:
        url_sha1 = sha1(url)  # url 的 hash 值
        pathed_url = Path(url)

        file_name = url_sha1 + pathed_url.suffix
        file_path = CACHE_DIR.joinpath(file_name)

        if not file_path.exists():  # 若文件不存在，则下载
            async with httpx.AsyncClient(headers=REQUEST_HEADERS, timeout=10) as client:
                try:
                    response = await client.get(url)
                except UnsupportedProtocol:
                    logger.error("链接不支持 url[%s]", url)
                    return ""

                if response.is_error:
                    logger.error("请求出现错误 url[%s] status_code[%s]", url, response.status_code)
                    raise UrlResourcesNotFoundError(url)

                if response.status_code != 200:
                    logger.error("download_resource 获取url[%s] 错误 status_code[%s]", url, response.status_code)
                    raise UrlResourcesNotFoundError(url)

            async with aiofiles.open(file_path, mode="wb") as f:
                await f.write(response.content)

        logger.debug("download_resource 获取url[%s] 并下载到 file_dir[%s]", url, file_path)

        return file_path if return_path else Path(file_path).as_uri()

    @staticmethod
    def get_args(context: CallbackContext) -> List[str]:
        args = context.args
        match = context.match

        if args is None:
            if match is not None and (command := match.groups()[0]):
                temp = []
                command_parts = command.split(" ")
                for command_part in command_parts:
                    if command_part:
                        temp.append(command_part)
                return temp
            return []
        if len(args) >= 1:
            return args
        return []


class ConversationFuncs:
    @conversation.fallback
    @handler.command(command="cancel", block=False)
    async def cancel(self, update: Update, _) -> int:
        await update.effective_message.reply_text("退出命令", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
