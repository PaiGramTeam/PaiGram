from telegram import Update
from telegram.ext import ContextTypes

from core.plugin import Plugin, handler
from core.services.users.services import UserAdminService
from utils.log import logger


class AdminPlugin(Plugin):
    """有关BOT ADMIN处理"""

    def __init__(self, user_admin_service: UserAdminService = None):
        self.user_admin_service = user_admin_service

    @handler.command("add_admin", block=False, admin=True)
    async def add_admin(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        reply_to_message = message.reply_to_message
        user = update.effective_user
        logger.info("用户 %s[%s] add_admin 命令请求", user.full_name, user.id)
        if reply_to_message:
            from_user = reply_to_message.from_user
            if from_user:
                if await self.user_admin_service.add_admin(from_user.id):
                    logger.success("成功添加用户 %s[%s] 到Bot的管理员权限", from_user.full_name, from_user.id)
                    await message.reply_text("添加成功")
                else:
                    await message.reply_text("该用户已经存在管理员列表")
            else:
                await message.reply_text("回复的用户不存在")
        else:
            await message.reply_text("请回复对应消息")

    @handler.command("del_admin", block=False, admin=True)
    async def del_admin(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        reply_to_message = message.reply_to_message
        user = update.effective_user
        logger.info("用户 %s[%s] del_admin 命令请求", user.full_name, user.id)
        if reply_to_message:
            from_user = reply_to_message.from_user
            if from_user:
                if await self.user_admin_service.delete_admin(from_user.id):
                    logger.success("成功移除用户 %s[%s] 在Bot的管理员权限", from_user.full_name, from_user.id)
                    await message.reply_text("移除成功")
                else:
                    await message.reply_text("移除失败 该用户不存在管理员列表")
            else:
                await message.reply_text("回复的用户不存在")
        else:
            await message.reply_text("请回复对应消息")
