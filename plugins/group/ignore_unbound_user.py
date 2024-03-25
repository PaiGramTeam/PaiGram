from typing import TYPE_CHECKING

from telegram.constants import ChatType
from telegram.ext import ApplicationHandlerStop, filters

from gram_core.dependence.redisdb import RedisDB
from gram_core.plugin import Plugin, handler, HandlerData
from gram_core.services.groups.services import GroupService
from gram_core.services.players import PlayersService
from gram_core.services.users.services import UserAdminService
from plugins.tools.chat_administrators import ChatAdministrators
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update, Message
    from telegram.ext import ContextTypes


class IgnoreUnboundUser(Plugin):
    def __init__(
        self,
        players_service: PlayersService,
        group_service: GroupService,
        user_admin_service: UserAdminService,
        redis: RedisDB,
    ):
        self.players_service = players_service
        self.group_service = group_service
        self.user_admin_service = user_admin_service
        self.cache = redis.client

    async def initialize(self) -> None:
        self.application.run_preprocessor(self.check_update)

    async def check_account(self, user_id: int) -> bool:
        return bool(await self.players_service.get_player(user_id))

    async def check_group(self, group_id: int) -> bool:
        return await self.group_service.is_ignore(group_id)

    async def check_update(self, update: "Update", _, __, context: "ContextTypes.DEFAULT_TYPE", data: "HandlerData"):
        if not isinstance(data, HandlerData):
            return
        if not data.player:
            return
        chat = update.effective_chat
        if (not chat) or chat.type not in [ChatType.SUPERGROUP, ChatType.GROUP]:
            return
        if not await self.check_group(chat.id):
            # 未开启此功能
            return
        message = update.effective_message
        if message:
            text = message.text or message.caption
            if text and context.bot.username in text:
                # 机器人被提及
                return
        uid = await self.get_real_user_id(update)
        if await self.check_account(uid):
            # 已绑定账号
            return
        self.log_user(update, logger.info, "群组 %s[%s] 拦截了未绑定用户触发命令", chat.title, chat.id)
        raise ApplicationHandlerStop

    async def check_permission(self, chat_id: int, user_id: int, context: "ContextTypes.DEFAULT_TYPE") -> bool:
        if await self.user_admin_service.is_admin(user_id):
            return True
        admins = await ChatAdministrators.get_chat_administrators(self.cache, context, chat_id)
        return ChatAdministrators.is_admin(admins, user_id)

    async def reply_and_delete(self, message: "Message", text: str):
        reply = await message.reply_text(text)
        self.add_delete_message_job(message)
        self.add_delete_message_job(reply)

    @handler.command("ignore_unbound_user", filters=filters.ChatType.SUPERGROUP | filters.ChatType.GROUP, block=False)
    async def ignore_unbound_user(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        chat_id = update.effective_chat.id
        if not await self.check_permission(chat_id, user_id, context):
            await self.reply_and_delete(message, "您没有权限执行此操作")
            return
        self.log_user(update, logger.info, "更改群组 未绑定用户触发命令 功能状态")
        group = await self.group_service.get_group_by_id(chat_id)
        if not group:
            await self.reply_and_delete(message, "群组信息出现错误，请尝试重新添加机器人到群组")
            return
        group.is_ignore = not group.is_ignore
        await self.group_service.update_group(group)
        await message.reply_text("已" + ("开启" if group.is_ignore else "关闭") + "忽略未绑定用户触发命令功能")
