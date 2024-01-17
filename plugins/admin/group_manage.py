from typing import TYPE_CHECKING, Optional

from telegram.constants import ChatType
from telegram.error import BadRequest, Forbidden
from telegram.ext import ChatMemberHandler

from core.handler.grouphandler import GroupHandler
from core.plugin import Plugin, handler
from core.services.groups import GroupService
from core.services.groups.models import GroupDataBase as Group
from core.services.users import UserBanService
from utils.chatmember import extract_status_change
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class GroupManage(Plugin):
    def __init__(
        self,
        group_service: GroupService,
        user_ban_service: UserBanService,
    ):
        self.type_handler = None
        self.group_service = group_service
        self.user_ban_service = user_ban_service

    async def initialize(self) -> None:
        self.type_handler = GroupHandler(self.application)
        self.application.telegram.add_handler(self.type_handler, group=-2)

    async def shutdown(self) -> None:
        self.application.telegram.remove_handler(self.type_handler, group=-2)

    @handler.chat_member(chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER, block=False)
    async def check_group(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        result = extract_status_change(update.my_chat_member)
        if result is None:
            return
        was_member, is_member = result
        chat = update.effective_chat
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
            return
        if not was_member and is_member:
            if await self.group_service.is_banned(chat.id):
                logger.info("会话 %s[%s] 在黑名单中，尝试退出", chat.title, chat.id)
                await GroupHandler.leave_chat(context.bot, chat.id)
                return
            if await self.group_service.is_need_update(chat.id):
                await GroupHandler.update_group(context.bot, self.group_service, chat)
            else:
                await self.group_service.join(chat.id)
        if was_member and not is_member:
            await self.group_service.leave(chat.id)

    def get_chat_id(self, context: "ContextTypes.DEFAULT_TYPE") -> Optional[int]:
        args = self.get_args(context)
        if args:
            try:
                return int(args[0])
            except ValueError:
                return None

    async def add_block_group(self, chat_id: int):
        group = await self.group_service.get_group_by_id(chat_id)
        if group:
            group.is_banned = True
            await self.group_service.update_group(group)
        else:
            chat = None
            try:
                chat = await self.get_chat(chat_id)
            except (BadRequest, Forbidden) as exc:
                logger.warning("通过 id 获取会话信息失败，API 返回：%s", str(exc))
            if chat:
                group = Group.from_chat(chat)
            else:
                group = Group.from_id(chat_id)
            group.is_banned = True
            await self.group_service.update_group(group)

    @handler.command(command="add_block", block=False, admin=True)
    @handler.callback_query(pattern=r"^block\|add\|", block=False, admin=True)
    async def add_block(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        callback_query = update.callback_query
        user = update.effective_user
        message = update.effective_message
        chat_id = self.get_chat_id(context) if not callback_query else int(callback_query.data.split("|")[2])
        logger.info(
            "用户 %s[%s] add_block 命令请求 chat_id[%s] callback[%s]", user.full_name, user.id, chat_id, bool(callback_query)
        )
        if not chat_id:
            await message.reply_text("参数错误，请指定群 id ！")
            return

        async def reply(text: str):
            if callback_query:
                await callback_query.answer(text, show_alert=True)
            else:
                await message.reply_text(text)

        if chat_id < 0:
            if await self.group_service.is_banned(chat_id):
                await reply("该群已在黑名单中！")
                return
            await self.add_block_group(chat_id)
            await reply("已将该群加入黑名单！")
        else:
            if await self.user_ban_service.is_banned(chat_id):
                await reply("该用户已在黑名单中！")
                return
            try:
                await self.user_ban_service.add_ban(chat_id)
            except PermissionError:
                await reply("无法操作管理员！")
                return
            await reply("已将该用户加入黑名单！")

    @handler.command(command="del_block", block=False, admin=True)
    @handler.callback_query(pattern=r"^block\|del\|", block=False, admin=True)
    async def del_block(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        callback_query = update.callback_query
        user = update.effective_user
        message = update.effective_message
        chat_id = self.get_chat_id(context) if not callback_query else int(callback_query.data.split("|")[2])
        logger.info(
            "用户 %s[%s] del_block 命令请求 chat_id[%s] callback[%s]", user.full_name, user.id, chat_id, bool(callback_query)
        )
        if not chat_id:
            await message.reply_text("参数错误，请指定群 id ！")
            return

        async def reply(text: str):
            if callback_query:
                await callback_query.answer(text, show_alert=True)
            else:
                await message.reply_text(text)

        if chat_id < 0:
            if not await self.group_service.is_banned(chat_id):
                await reply("该群不在黑名单中！")
                return
            success = await self.group_service.del_ban(chat_id)
            if not success:
                await reply("该群不在黑名单中！")
                return
            await reply("已将该群移出黑名单！")
        else:
            if not await self.user_ban_service.is_banned(chat_id):
                await reply("该用户不在黑名单中！")
                return
            try:
                success = await self.user_ban_service.del_ban(chat_id)
                if not success:
                    await reply("该用户不在黑名单中！")
                    return
            except PermissionError:
                await reply("无法操作管理员！")
                return
            await reply("已将该用户移出黑名单！")
