import datetime
import time
from functools import wraps
from typing import Callable, Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler, filters

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
    def __init__(self, service: BaseService, auth_callback: Callable):
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


def restricts(filters_chat: filters = filters.ALL, return_data=None, try_delete_message: bool = False,
              restricts_time: int = 5):
    """
        用于装饰在指定函数防止洪水调用的装饰器

        被修饰的函数生声明()必须为
        async def command_func(update, context)
        或
        async def command_func(self, update, context)

        如果修饰的函数属于
        ConversationHandler
        参数
        return_data
        必须传入
        ConversationHandler.END

        我真™是服了某些闲着没事干的群友了
    """

    def decorator(func: Callable):
        @wraps(func)
        async def restricts_func(*args, **kwargs):
            update: Optional[Update] = None
            context: Optional[CallbackContext] = None
            if len(args) == 3:
                # self update context
                _, update, context = args
            elif len(args) == 2:
                # update context
                update, context = args
            else:
                return await func(*args, **kwargs)
            message = update.message
            user = update.effective_user
            if filters_chat.filter(message):
                command_time = context.user_data.get("command_time", 0)
                count = context.user_data.get("usage_count", 0)
                restrict_since = context.user_data.get("restrict_since", 0)
                # 洪水防御
                if restrict_since:
                    if (time.time() - restrict_since) >= 60 * 5:
                        del context.user_data["restrict_since"]
                        del context.user_data["usage_count"]
                    else:
                        return return_data
                else:
                    if count == 5:
                        context.user_data["restrict_since"] = time.time()
                        await update.effective_message.reply_text("你已经触发洪水防御，请等待5分钟")
                        Log.warning(f"用户 {user.full_name}[{user.id}] 触发洪水限制 已被限制5分钟")
                        return return_data
                # 单次使用限制
                if command_time:
                    if (time.time() - command_time) <= restricts_time:
                        context.user_data["usage_count"] = count + 1
                        if filters.ChatType.GROUPS.filter(message):
                            if try_delete_message:
                                try:
                                    await message.delete()
                                except BadRequest as error:
                                    Log.warning("删除消息失败", error)
                            return return_data
                    else:
                        if count >= 1:
                            context.user_data["usage_count"] = count - 1

                context.user_data["command_time"] = time.time()

            return await func(*args, **kwargs)

        return restricts_func

    return decorator
