from telegram import Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext

from logger import Log
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

    async def leave_chat(self, update: Update, context: CallbackContext):
        message = update.message
        user = message.from_user
        admin_list = await self.service.admin.get_admin_list()
        if user.id in admin_list:
            try:
                args = message.text.split()
                if len(args) >= 2:
                    char_id = int(args[1])
                else:
                    await message.reply_text("输入错误")
                    return
            except ValueError as error:
                Log.error(f"获取 char_id 发生错误！ 错误信息为 \n", error)
                await message.reply_text("输入错误")
                return
            try:
                try:
                    char = await context.bot.get_chat(char_id)
                    await message.reply_text(f"正在尝试退出群 {char.title}[{char.id}]")
                except (BadRequest, Forbidden):
                    pass
                await context.bot.leave_chat(char_id)
            except (BadRequest, Forbidden) as error:
                Log.error(f"退出 char_id[{char_id}] 发生错误！ 错误信息为 \n", error)
                await message.reply_text(f"退出 char_id[{char_id}] 发生错误！ 错误信息为 {str(error)}")
                return
            await message.reply_text(f"退出 char_id[{char_id}] 成功！")
        else:
            await message.reply_text("权限不足")
