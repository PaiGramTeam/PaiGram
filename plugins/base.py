import asyncio
from typing import List, Tuple, Callable

from telegram import Update
from telegram.ext import CallbackContext, filters

from core.admin.services import BotAdminService
from utils.log import logger


class NewChatMembersHandler:

    def __init__(self, bot_admin_service: BotAdminService = None):
        self.bot_admin_service = bot_admin_service
        self.callback: List[Tuple[Callable, int]] = []

    def add_callback(self, callback, chat_id: int):
        if chat_id >= 0:
            raise ValueError
        self.callback.append((callback, chat_id))

    async def new_member(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        chat = message.chat
        from_user = message.from_user
        quit_status = False
        if filters.ChatType.GROUPS.filter(message):
            for user in message.new_chat_members:
                if user.id == context.bot.id:
                    if from_user is not None:
                        logger.info(f"用户 {from_user.full_name}[{from_user.id}] 在群 {chat.title}[{chat.id}] 邀请BOT")
                        admin_list = await self.bot_admin_service.get_admin_list()
                        if from_user.id in admin_list:
                            await context.bot.send_message(message.chat_id,
                                                           '感谢邀请小派蒙到本群！请使用 /help 查看咱已经学会的功能。')
                        else:
                            quit_status = True
                    else:
                        logger.info(f"未知用户 在群 {chat.title}[{chat.id}] 邀请BOT")
                        quit_status = True
        if quit_status:
            logger.warning("不是管理员邀请！退出群聊。")
            await context.bot.send_message(message.chat_id, "派蒙不想进去！不是旅行者的邀请！")
            await context.bot.leave_chat(chat.id)
        else:
            tasks = []
            for callback, chat_id in self.callback:
                if chat.id == chat_id:
                    task = asyncio.create_task(callback(update, context))
                    tasks.append(task)
            if len(tasks) >= 1:
                await asyncio.gather(*tasks)
