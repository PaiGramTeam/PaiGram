from telegram import Update
from telegram.ext import CallbackContext

from plugins.base import BasePlugins
from service import BaseService


class Admin(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)

    async def add_admin(self, update: Update, context: CallbackContext):
        message = update.message
        user = message.from_user
        reply_to_message = message.reply_to_message
        admin_list = await self.service.admin.get_admin_list()
        if user.id in admin_list:
            if reply_to_message is None:
                await message.reply_text("请回复对应消息")
            else:
                if reply_to_message.from_user.id in admin_list:
                    await message.reply_text("该用户已经存在管理员列表")
                else:
                    await self.service.admin.add_admin(reply_to_message.from_user.id)
                    await message.reply_text("添加成功")
        else:
            await message.reply_text("权限不足")

    async def del_admin(self, update: Update, context: CallbackContext):
        message = update.message
        user = message.from_user
        reply_to_message = message.reply_to_message
        admin_list = await self.service.admin.get_admin_list()
        if user.id in admin_list:
            if reply_to_message is None:
                await message.reply_text("请回复对应消息")
            else:
                if reply_to_message.from_user.id in admin_list:
                    await self.service.admin.delete_admin(reply_to_message.from_user.id)
                    await message.reply_text("删除成功")
                else:
                    await message.reply_text("该用户不存在管理员列表")
        else:
            await message.reply_text("权限不足")
