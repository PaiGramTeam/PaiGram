import datetime

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.ext._utils.types import HandlerCallback, CCT, RT

from logger import Log
from model.helpers import get_admin_list
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
                Log.warning(f"定时删除消息 chat_id[{chat_id}] message_id[{message_id}]失败 消息不存在")
            elif "Message can't be deleted" in str(error):
                Log.warning(f"定时删除消息 chat_id[{chat_id}] message_id[{message_id}]失败 消息无法删除 可能是没有授权")
            else:
                Log.warning(f"定时删除消息 chat_id[{chat_id}] message_id[{message_id}]失败 \n", error)
        return False

    def _add_delete_message_job(self, context: CallbackContext, chat_id: int, message_id: int,
                                delete_seconds: int = 60):
        context.job_queue.scheduler.add_job(self._clean, "date",
                                            id=f"{chat_id}|{message_id}|auto_clean_message",
                                            name=f"{chat_id}|{message_id}|auto_clean_message",
                                            args=[context, chat_id, message_id],
                                            run_date=context.job_queue._tz_now() + datetime.timedelta(
                                                seconds=delete_seconds), replace_existing=True)


class NewChatMembersHandler:
    def __init__(self, service: BaseService, auth_callback: HandlerCallback[Update, CCT, RT]):
        self.service = service
        self.auth_callback = auth_callback

    async def new_member(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        chat = message.chat
        from_user = message.from_user
        self.service.admin.get_admin_list()
        if filters.ChatType.GROUPS.filter(message):
            for user in message.new_chat_members:
                if user.id == context.bot.id:
                    if from_user is not None:
                        admin_list = await self.service.admin.get_admin_list()
                        if from_user.id in admin_list:
                            await context.bot.send_message(message.chat_id,
                                                           '感谢邀请小派蒙到本群！请使用 /help 查看咱已经学会的功能。')
                        else:
                            await context.bot.send_message(message.chat_id, "派蒙不想进去！不是旅行者的邀请！")
                            await context.bot.leave_chat(chat.id)
                    else:
                        await context.bot.leave_chat(chat.id)
        await self.auth_callback(update, context)
