from typing import Callable

from telegram import Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, CommandHandler

from logger import Log
from manager import listener_plugins_class
from utils.base import PaimonContext


def bot_admins_only(func: Callable) -> Callable:  # noqa
    async def decorator(self, update: Update, context: PaimonContext):
        service = context.service
        admin_list = await service.admin.get_admin_list()
        if update.message.from_user.id in admin_list:
            return await func(self, update, context)
        else:
            await update.message.reply_text("权限不足")
            return None

    return decorator


@listener_plugins_class()
class Admin:
    """有关BOT ADMIN处理
    """

    @classmethod
    def create_handlers(cls) -> list:
        admin = cls()
        return [
            CommandHandler("add_admin", admin.add_admin, block=False),
            CommandHandler("del_admin", admin.del_admin, block=False),
            CommandHandler("leave_chat", admin.leave_chat, block=False),
        ]

    @bot_admins_only
    async def add_admin(self, update: Update, context: PaimonContext):
        message = update.message
        reply_to_message = message.reply_to_message
        service = context.service
        admin_list = await service.admin.get_admin_list()
        if reply_to_message is None:
            await message.reply_text("请回复对应消息")
        else:
            if reply_to_message.from_user.id in admin_list:
                await message.reply_text("该用户已经存在管理员列表")
            else:
                await service.admin.add_admin(reply_to_message.from_user.id)
                await message.reply_text("添加成功")

    @bot_admins_only
    async def del_admin(self, update: Update, context: PaimonContext):
        message = update.message
        reply_to_message = message.reply_to_message
        service = context.service
        admin_list = await service.admin.get_admin_list()
        if reply_to_message is None:
            await message.reply_text("请回复对应消息")
        else:
            if reply_to_message.from_user.id in admin_list:
                await service.admin.delete_admin(reply_to_message.from_user.id)
                await message.reply_text("删除成功")
            else:
                await message.reply_text("该用户不存在管理员列表")

    @bot_admins_only
    async def leave_chat(self, update: Update, context: CallbackContext):
        message = update.message
        try:
            args = message.text.split()
            if len(args) >= 2:
                chat_id = int(args[1])
            else:
                await message.reply_text("输入错误")
                return
        except ValueError as error:
            Log.error("获取 chat_id 发生错误！ 错误信息为 \n", error)
            await message.reply_text("输入错误")
            return
        try:
            try:
                char = await context.bot.get_chat(chat_id)
                await message.reply_text(f"正在尝试退出群 {char.title}[{char.id}]")
            except (BadRequest, Forbidden):
                pass
            await context.bot.leave_chat(chat_id)
        except (BadRequest, Forbidden) as error:
            Log.error(f"退出 chat_id[{chat_id}] 发生错误！ 错误信息为 \n", error)
            await message.reply_text(f"退出 chat_id[{chat_id}] 发生错误！ 错误信息为 {str(error)}")
            return
        await message.reply_text(f"退出 chat_id[{chat_id}] 成功！")
