from typing import Optional

from telegram import Update, TelegramObject, User, ReplyKeyboardRemove
from telegram.ext import CallbackContext, filters, ConversationHandler

from core.baseplugin import BasePlugin
from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.cookies.models import Cookies
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
    cookies: Optional[Cookies] = None


CHECK_SERVER, DEL_USER = range(10800, 10802)


class UserPlugin(Plugin.Conversation, BasePlugin.Conversation):
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
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
            del_user_command_data.user = user_info
        except UserNotFoundError:
            await message.reply_text("用户未找到")
            return ConversationHandler.END
        cookies_status: bool = False
        try:
            cookies = await self.cookies_service.get_cookies(user.id, user_info.region)
            del_user_command_data.cookies = cookies
            cookies_status = True
        except CookiesNotFoundError:
            logger.info("用户 %s[%s] Cookies 不存在", user.full_name, user.id)
        if user_info.region == RegionEnum.HYPERION:
            uid = user_info.yuanshen_uid
            region_str = "米游社"
        elif user_info.region == RegionEnum.HOYOLAB:
            uid = user_info.genshin_uid
            region_str = "HoYoLab"
        else:
            await message.reply_text("数据非法")
            return ConversationHandler.END
        await message.reply_text("获取用户信息成功")
        text = (
            f"<b>绑定信息</b>\n"
            f"UID：<code>{uid}</code>\n"
            f"注册：<code>{region_str}</code>\n"
            f"是否绑定Cookie：<code>{'√' if cookies_status else '×'}</code>"
        )
        await message.reply_html(text)
        await message.reply_html("请回复<b>确认</b>即可解除绑定并从数据库移除，如绑定Cookies也会跟着一起从数据库删除，删除后操作无法逆转，回复 /cancel 可退出操作")
        return DEL_USER

    @conversation.state(state=DEL_USER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "确认":
            del_user_command_data: DelUserCommandData = context.chat_data.get("del_user_command_data")
            try:
                await self.user_service.del_user_by_id(user.id)
            except UserNotFoundError:
                await message.reply_text("用户未找到")
                return ConversationHandler.END
            else:
                logger.success("用户 %s[%s] 从数据库删除账号成功", user.full_name, user.id)
            if del_user_command_data.cookies:
                try:
                    await self.cookies_service.del_cookies(user.id, del_user_command_data.region)
                except CookiesNotFoundError:
                    logger.info("用户 %s[%s] Cookies 不存在", user.full_name, user.id)
                else:
                    logger.success("用户 %s[%s] 从数据库删除Cookies成功", user.full_name, user.id)
            await message.reply_text("删除成功")
            return ConversationHandler.END
        else:
            await message.reply_text("回复错误，退出当前会话")
            return ConversationHandler.END
