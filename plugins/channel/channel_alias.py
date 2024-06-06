from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from telegram.constants import ChatAction, ChatMemberStatus, ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import filters

from core.config import config
from core.plugin import Plugin, handler
from gram_core.services.channels.models import ChannelAliasDataBase as ChannelAlias
from gram_core.services.channels.services import ChannelAliasService
from gram_core.services.groups.services import GroupService
from gram_core.services.players import PlayersService
from plugins.tools.genshin import PlayerNotFoundError
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Bot, Update, Message
    from telegram.ext import ContextTypes

__all__ = ("ChannelAliasPlugin",)

CHANNEL_ALIAS_OPEN = f"""成功开启频道透视模式，{config.notice.bot_name}将会把你当做普通用户，现在你可以使用频道身份执行命令

- 此功能可能使其他人能看到你的个人账号身份。
- 此功能开启后对所有群组均有效。
- 在转让频道前，请务必关闭此功能。
"""
CHANNEL_ALIAS_CLOSE = f"""成功关闭频道透视模式，{config.notice.bot_name}将不会把你当做普通用户，现在你无法使用频道身份执行命令"""
CHANNEL_ADMIN_HELP = (
    "参数错误，可用命令：\n\n- disable <id> 关闭频道透视模式\n- change <cid> <uid> 强制设置频道透视对应的用户 id"
)


class ChannelAliasError(Exception):
    def __init__(self, message: str):
        self.message = message


class ChannelAliasPlugin(Plugin):
    def __init__(
        self,
        group_service: GroupService,
        players_service: PlayersService,
        channel_alias_service: ChannelAliasService,
    ):
        self.group_service = group_service
        self.players_service = players_service
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

    async def add_channel_alias_db(self, channel_id: int, owner_id: int):
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

    async def channel_alias_add(self, bot: "Bot", channel_id: int):
        info = await self.group_service.get_group_by_id(channel_id)
        if (not info) or info.is_left:
            raise ChannelAliasError("未邀请 BOT 到你的频道，请先邀请 BOT 到你的频道")
        if info.is_banned:
            raise ChannelAliasError("此频道位于黑名单中，请联系管理员")
        owner_id = await self.get_channel_owner(bot, channel_id)
        if not owner_id:
            raise ChannelAliasError("未获取到频道拥有者，请联系管理员")
        if not self.players_service.get_player(owner_id):
            raise PlayerNotFoundError(owner_id)
        await self.add_channel_alias_db(channel_id, owner_id)

    async def channel_alias_remove(self, channel_id: int):
        alias_db = await self.channel_alias_service.get_by_chat_id(channel_id)
        if alias_db:
            alias_db.is_valid = False
            alias_db.updated_at = datetime.now()
            await self.channel_alias_service.update_channel_alias(alias_db)

    @handler.command(command="channel_alias", filters=filters.SenderChat.CHANNEL, block=False)
    async def channel_alias(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        self.log_user(update, logger.info, "发出 channel_alias 命令")
        await message.reply_chat_action(ChatAction.TYPING)
        channel_id = message.sender_chat.id
        uid = await self.channel_alias_service.get_uid_by_chat_id(channel_id, is_valid=True)
        if not uid:
            reply = await message.reply_text("检查中，请稍候")
            try:
                await self.channel_alias_add(context.bot, channel_id)
                reply = await reply.edit_text(CHANNEL_ALIAS_OPEN)
            except PlayerNotFoundError as exc:
                if filters.ChatType.GROUPS.filter(message):
                    self.add_delete_message_job(reply, delay=1)
                raise exc
            except ChannelAliasError as exc:
                reply = await reply.edit_text(str(exc))
        else:
            try:
                await self.channel_alias_remove(channel_id)
                reply = await message.reply_text(CHANNEL_ALIAS_CLOSE)
            except ChannelAliasError as exc:
                reply = await message.reply_text(str(exc))
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
            self.add_delete_message_job(reply)

    async def channel_alias_admin_disable(self, args: List[str], message: "Message"):
        if len(args) < 2:
            await message.reply_text("参数错误，可用命令：\n\n- disable <id> 关闭频道透视模式")
            return
        try:
            chat_id = int(args[1])
        except ValueError:
            await message.reply_text("参数错误，频道 id 必须为整数")
            return
        try:
            await self.channel_alias_remove(chat_id)
            await message.reply_text(f"成功关闭频道透视模式，频道 id[{chat_id}]")
        except ChannelAliasError as exc:
            await message.reply_text(str(exc))

    async def channel_alias_admin_change(self, args: List[str], message: "Message"):
        if len(args) < 3:
            await message.reply_text("参数错误，可用命令：\n\n- change <cid> <uid> 强制设置频道透视对应的用户 id")
            return
        try:
            chat_id = int(args[1])
            user_id = int(args[2])
        except ValueError:
            await message.reply_text("参数错误，频道或者用户 id 必须为整数")
            return
        await self.add_channel_alias_db(chat_id, user_id)
        await message.reply_text(f"成功设置频道透视对应的用户 id，频道 id[{chat_id}] 用户 id[{user_id}]")

    async def channel_alias_admin_info(self, args: List[str], message: "Message"):
        if len(args) < 2:
            await message.reply_text("参数错误，可用命令：\n\n- info <id> 获取频道透视信息")
            return
        try:
            chat_id = int(args[1])
        except ValueError:
            await message.reply_text("参数错误，频道 id 必须为整数")
            return
        alias_db = await self.channel_alias_service.get_by_chat_id(chat_id)
        if alias_db:
            text = f"频道 id：`{chat_id}`\n"
            text += f"用户 id：`{alias_db.user_id}`\n"
            text += f"是否有效：`{'是' if alias_db.is_valid else '否'}`\n"
            if alias_db.created_at:
                text += f"创建时间：`{alias_db.created_at.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            if alias_db.updated_at:
                text += f"更新时间：`{alias_db.updated_at.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            await message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await message.reply_text(f"频道 id `{chat_id}` 未设置频道透视信息", parse_mode=ParseMode.MARKDOWN_V2)

    @handler.command(command="channel_alias_admin", block=False, admin=True)
    async def channel_alias_admin(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        args = self.get_args(context)
        self.log_user(update, logger.info, "发出 channel_alias_admin 命令 args[%s]", args)
        await message.reply_chat_action(ChatAction.TYPING)
        if not args:
            await message.reply_text(CHANNEL_ADMIN_HELP)
            return
        method = args[0]
        if method == "disable":
            await self.channel_alias_admin_disable(args, message)
        elif method == "change":
            await self.channel_alias_admin_change(args, message)
        elif method == "info":
            await self.channel_alias_admin_info(args, message)
        else:
            await message.reply_text(CHANNEL_ADMIN_HELP)
