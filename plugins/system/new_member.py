from telegram import Update
from telegram.ext import CallbackContext

from core.admin import BotAdminService
from core.plugin import Plugin, handler
from utils.log import logger


class BotJoiningGroupsVerification(Plugin):
    def __init__(self, bot_admin_service: BotAdminService = None):
        self.bot_admin_service = bot_admin_service

    @handler.message.new_chat_members(priority=1)
    async def new_member(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        chat = message.chat
        from_user = message.from_user
        quit_status = False
        for new_chat_members_user in message.new_chat_members:
            if new_chat_members_user.id == context.bot.id:
                logger.info(f"有人邀请BOT进入群 {chat.title}[{chat.id}]")
                quit_status = True
                if from_user is not None:
                    logger.info(f"用户 {from_user.full_name}[{from_user.id}] 在群 {chat.title}[{chat.id}] 邀请BOT")
                    admin_list = await self.bot_admin_service.get_admin_list()
                    if from_user.id in admin_list:
                        await context.bot.send_message(message.chat_id, "感谢邀请小派蒙到本群！请使用 /help 查看咱已经学会的功能。")
                        quit_status = False
                else:
                    logger.info(f"未知用户 在群 {chat.title}[{chat.id}] 邀请BOT")
        if quit_status:
            logger.warning("不是管理员邀请！退出群聊。")
            await context.bot.send_message(message.chat_id, "派蒙不想进去！不是旅行者的邀请！")
            await context.bot.leave_chat(chat.id)
