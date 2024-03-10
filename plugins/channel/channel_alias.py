from datetime import datetime
from typing import TYPE_CHECKING, Optional

from telegram import Update
from telegram.constants import ChatAction, ChatMemberStatus
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, filters

from core.plugin import Plugin, handler
from gram_core.services.channels.models import ChannelAliasDataBase as ChannelAlias
from gram_core.services.channels.services import ChannelAliasService
from gram_core.services.groups.services import GroupService
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Bot

__all__ = ("ChannelAliasPlugin",)

CHANNEL_ALIAS_OPEN = """成功开启频道透视模式，派蒙将会把你当做普通用户，现在你可以使用频道身份执行命令

- 此功能可能使其他人能看到你的个人账号身份。
- 此功能开启后对所有群组均有效。
- 在转让频道前，请务必关闭此功能。
"""
CHANNEL_ALIAS_CLOSE = """成功关闭频道透视模式，派蒙将不会把你当做普通用户，现在你无法使用频道身份执行命令"""


class ChannelAliasError(Exception):
    def __init__(self, message: str):
        self.message = message


class ChannelAliasPlugin(Plugin):
    def __init__(
            self,
            group_service: GroupService,
            channel_alias_service: ChannelAliasService,
    ):
        self.group_service = group_service
        self.channel_alias_service = channel_alias_service

    @staticmethod
    async def get_channel_owner(bot: "Bot", channel_id: int) -> Optional[int]:
        try:
            chat_administrators = await bot.get_chat_administrators(channel_id)
            for admin in chat_administrators:
                if admin.status == ChatMemberStatus.OWNER:
                    return admin.user.id
        except (BadRequest, Forbidden) as exc:
            logger.warning("通过 id 获取频道管理员信息失败，API 返回：%s", str(exc))
            raise ChannelAliasError("获取频道管理员信息失败，请先邀请 BOT 到你的频道")

    async def channel_alias_add(self, bot: "Bot", channel_id: int):
        info = await self.group_service.get_group_by_id(channel_id)
        if (not info) or info.is_left:
            raise ChannelAliasError("未邀请 BOT 到你的频道，请先邀请 BOT 到你的频道")
        if info.is_banned:
            raise ChannelAliasError("此频道位于黑名单中，请联系管理员")
        owner_id = await self.get_channel_owner(bot, channel_id)
        if not owner_id:
            raise ChannelAliasError("未获取到频道拥有者，请联系管理员")
        alias_db = await self.channel_alias_service.get_by_chat_id(channel_id)
        if alias_db:
            alias_db.user_id = owner_id
            alias_db.is_valid = True
            alias_db.updated_at = datetime.now()
            await self.channel_alias_service.update_channel_alias(alias_db)
        else:
            alias_db = ChannelAlias(
                chat_id=channel_id,
                user_id=owner_id,
                is_valid=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            await self.channel_alias_service.add_channel_alias(alias_db)

    async def channel_alias_remove(self, channel_id: int):
        alias_db = await self.channel_alias_service.get_by_chat_id(channel_id)
        if alias_db:
            alias_db.is_valid = False
            alias_db.updated_at = datetime.now()
            await self.channel_alias_service.update_channel_alias(alias_db)

    @handler.command(command="channel_alias", filters=filters.SenderChat.CHANNEL, block=False)
    async def channel_alias(self, update: Update, context: CallbackContext):
        message = update.effective_message
        self.log_user(update, logger.info, "发出 channel_alias 命令")
        await message.reply_chat_action(ChatAction.TYPING)
        channel_id = message.sender_chat.id
        uid = await self.channel_alias_service.get_uid_by_chat_id(channel_id, is_valid=True)
        try:
            if not uid:
                await self.channel_alias_add(context.bot, channel_id)
                reply = await message.reply_text(CHANNEL_ALIAS_OPEN)
            else:
                await self.channel_alias_remove(channel_id)
                reply = await message.reply_text(CHANNEL_ALIAS_CLOSE)
        except ChannelAliasError as exc:
            reply = await message.reply_text(str(exc))
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
            self.add_delete_message_job(reply)
