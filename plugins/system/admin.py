import contextlib

from telegram import Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, CommandHandler

from core.admin import BotAdminService
from core.plugin import handler, Plugin
from utils.decorators.admins import bot_admins_rights_check
from utils.log import logger


class AdminPlugin(Plugin):
    """有关BOT ADMIN处理"""

    def __init__(self, bot_admin_service: BotAdminService = None):
        self.bot_admin_service = bot_admin_service

    @handler(CommandHandler, command="add_admin", block=False)
    @bot_admins_rights_check
    async def add_admin(self, update: Update, _: CallbackContext):
        message = update.effective_message
        reply_to_message = message.reply_to_message
        if reply_to_message is None:
            await message.reply_text("请回复对应消息")
        else:
            admin_list = await self.bot_admin_service.get_admin_list()
            if reply_to_message.from_user.id in admin_list:
                await message.reply_text("该用户已经存在管理员列表")
            else:
                await self.bot_admin_service.add_admin(reply_to_message.from_user.id)
                await message.reply_text("添加成功")

    @handler(CommandHandler, command="del_admin", block=False)
    @bot_admins_rights_check
    async def del_admin(self, update: Update, _: CallbackContext):
        message = update.effective_message
        reply_to_message = message.reply_to_message
        admin_list = await self.bot_admin_service.get_admin_list()
        if reply_to_message is None:
            await message.reply_text("请回复对应消息")
        else:
            if reply_to_message.from_user.id in admin_list:
                await self.bot_admin_service.delete_admin(reply_to_message.from_user.id)
                await message.reply_text("删除成功")
            else:
                await message.reply_text("该用户不存在管理员列表")

    @handler(CommandHandler, command="leave_chat", block=False)
    @bot_admins_rights_check
    async def leave_chat(self, update: Update, context: CallbackContext):
        message = update.effective_message
        try:
            args = message.text.split()
            if len(args) >= 2:
                chat_id = int(args[1])
            else:
                await message.reply_text("输入错误")
                return
        except ValueError as error:
            logger.error("获取 chat_id 发生错误！ 错误信息为 \n", exc_info=error)
            await message.reply_text("输入错误")
            return
        try:
            with contextlib.suppress(BadRequest, Forbidden):
                chat = await context.bot.get_chat(chat_id)
                await message.reply_text(f"正在尝试退出群 {chat.title}[{chat.id}]")
            await context.bot.leave_chat(chat_id)
        except (BadRequest, Forbidden) as exc:
            await message.reply_text(f"退出 chat_id[{chat_id}] 发生错误！ 错误信息为 {str(exc)}")
            return
        await message.reply_text(f"退出 chat_id[{chat_id}] 成功！")
