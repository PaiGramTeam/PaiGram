import datetime
import time
from typing import Callable, Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ChatType
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.ext._utils.types import HandlerCallback, CCT, RT

from logger import Log
from service import BaseService


async def clean_message(context: CallbackContext, chat_id: int, message_id: int) -> bool:
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except BadRequest as error:
        if "not found" in str(error):
            Log.warning(f"定时删除消息 chat_id[{chat_id}] message_id[{message_id}]失败 消息不存在")
        elif "Message can't be deleted" in str(error):
            Log.warning(f"定时删除消息 chat_id[{chat_id}] message_id[{message_id}]失败 消息无法删除 可能是没有授权")
        else:
            Log.warning(f"定时删除消息 chat_id[{chat_id}] message_id[{message_id}]失败 \n", error)
    return False


def add_delete_message_job(context: CallbackContext, chat_id: int, message_id: int,
                           delete_seconds: int = 60):
    context.job_queue.scheduler.add_job(clean_message, "date",
                                        id=f"{chat_id}|{message_id}|auto_clean_message",
                                        name=f"{chat_id}|{message_id}|auto_clean_message",
                                        args=[context, chat_id, message_id],
                                        run_date=context.job_queue._tz_now() + datetime.timedelta(
                                            seconds=delete_seconds), replace_existing=True)


class BasePlugins:
    def __init__(self, service: BaseService):
        self.service = service

    @staticmethod
    async def cancel(update: Update, _: CallbackContext) -> int:
        await update.message.reply_text("退出命令", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    @staticmethod
    async def _clean(context: CallbackContext, chat_id: int, message_id: int) -> bool:
        return await clean_message(context, chat_id, message_id)

    @staticmethod
    def _add_delete_message_job(context: CallbackContext, chat_id: int, message_id: int,
                                delete_seconds: int = 60):
        return add_delete_message_job(context, chat_id, message_id, delete_seconds)


class NewChatMembersHandler:
    def __init__(self, service: BaseService, auth_callback: HandlerCallback[Update, CCT, RT]):
        self.service = service
        self.auth_callback = auth_callback

    async def new_member(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        chat = message.chat
        from_user = message.from_user
        quit_status = False
        if filters.ChatType.GROUPS.filter(message):
            for user in message.new_chat_members:
                if user.id == context.bot.id:
                    if from_user is not None:
                        Log.info(f"用户 {from_user.full_name}[{from_user.id}] 在群 {chat.title}[{chat.id}] 邀请BOT")
                        admin_list = await self.service.admin.get_admin_list()
                        if from_user.id in admin_list:
                            await context.bot.send_message(message.chat_id,
                                                           '感谢邀请小派蒙到本群！请使用 /help 查看咱已经学会的功能。')
                        else:
                            quit_status = True
                    else:
                        Log.info(f"未知用户 在群 {chat.title}[{chat.id}] 邀请BOT")
                        quit_status = True
        if quit_status:
            Log.warning("不是管理员邀请！退出群聊。")
            await context.bot.send_message(message.chat_id, "派蒙不想进去！不是旅行者的邀请！")
            await context.bot.leave_chat(chat.id)
        await self.auth_callback(update, context)


class RestrictsCalls(object):
    """
    用于装饰在指定函数防止洪水调用的类装饰器
    """
    _user_time = {}
    _filters_chat = {}
    _return_data = {}
    _try_delete_message = {}

    def __init__(self, filters_chat: ChatType = filters.ChatType.GROUPS, return_data=None,
                 try_delete_message: bool = False):
        self.filters_chat = filters_chat
        self.return_data = return_data
        self.try_delete_message = try_delete_message

    def __call__(self, func: Callable):
        self._filters_chat[func] = self.filters_chat
        self._return_data[func] = self.return_data
        self._try_delete_message[func] = self.try_delete_message

        async def decorator(*args, **kwargs):
            update: Optional[Update] = None
            for arg in args:
                if isinstance(arg, Update):
                    update = arg
            if update is None:
                return await func(*args, **kwargs)
            message = update.message
            user = update.effective_user
            _filters = self._filters_chat.get(func)
            if _filters is None:
                raise KeyError("RestrictsCalls: filters not find")
            _return_data = self._return_data.get(func)
            _try_delete_message = self._return_data.get(func, False)
            if _filters.filter(message):
                try:
                    command_time = self._user_time.get(f"{user.id}")
                    if command_time is None:
                        self._user_time[f"{user.id}"] = time.time()
                    else:
                        if time.time() - command_time <= 20:
                            if _try_delete_message:
                                try:
                                    await message.delete()
                                except BadRequest as error:
                                    Log.warning("删除消息失败", error)
                            return _return_data
                        else:
                            self._user_time[f"{user.id}"] = time.time()
                except (ValueError, KeyError) as error:
                    Log.error("操作失败", error)
            return await func(*args, **kwargs)

        return decorator
