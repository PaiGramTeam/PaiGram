from typing import Optional

from telegram import Update, TelegramObject, User, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, filters, ConversationHandler
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler, conversation
from core.user import UserService
from core.user.error import UserNotFoundError
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger
from utils.models.base import RegionEnum


class DelUserCommandData(TelegramObject):
    user: Optional[User] = None
    region: RegionEnum = RegionEnum.HYPERION


CHECK_SERVER, DEL_USER, COMMAND_RESULT = range(10800, 10803)


class UserPlugin(Plugin, BasePlugin):
    def __init__(
        self,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
    ):
        self.cookies_service = cookies_service
        self.user_service = user_service

    @conversation.entry_point
    @handler.command(command="deluser", filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 删除账号命令请求", user.full_name, user.id)
        del_user_command_data: DelUserCommandData = context.chat_data.get("del_user_command_data")
        if del_user_command_data is None:
            del_user_command_data = DelUserCommandData()
            context.chat_data["del_user_command_data"] = del_user_command_data
        text = f'你好 {user.mention_markdown_v2()} {escape_markdown("！请选择要解除绑定账号所在的服务器！或回复退出取消操作")}'
        reply_keyboard = [["米游社", "HoYoLab"], ["退出"]]
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHECK_SERVER

    @conversation.state(state=CHECK_SERVER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        del_user_command_data: DelUserCommandData = context.chat_data.get("del_user_command_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "米游社":
            region = del_user_command_data.region = RegionEnum.HYPERION
        elif message.text == "HoYoLab":
            region = del_user_command_data.region = RegionEnum.HOYOLAB
        else:
            await message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
            del_user_command_data.user = user_info
            del_user_command_data.user = region
        except UserNotFoundError:
            await message.reply_text("用户未找到")
            return ConversationHandler.END
        await message.reply_text(
            "请回复确认即可解除绑定，如绑定Cookies也会跟着一起从数据库删除，删除后操作无法逆转，回复 /cancel 退出操作", reply_markup=ReplyKeyboardRemove()
        )
        return DEL_USER

    @conversation.state(state=DEL_USER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        del_user_command_data: DelUserCommandData = context.chat_data.get("del_user_command_data")
        try:
            await self.user_service.del_user_by_id(user.id)
        except UserNotFoundError:
            await message.reply_text("用户未找到")
            return ConversationHandler.END
        else:
            logger.success("用户 %s[%s] 从数据库删除账号成功", user.full_name, user.id)
        try:
            await self.cookies_service.del_cookies(user.id, del_user_command_data.region)
        except CookiesNotFoundError:
            logger.info("用户 %s[%s] Cookies 不存在", user.full_name, user.id)
        else:
            logger.success("用户 %s[%s] 从数据库删除Cookies成功", user.full_name, user.id)
        await message.reply_text("删除成功")
        return ConversationHandler.END
