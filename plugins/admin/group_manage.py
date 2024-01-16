from typing import TYPE_CHECKING

from telegram.constants import ChatType
from telegram.ext import ChatMemberHandler

from core.handler.grouphandler import GroupHandler
from core.plugin import Plugin, handler
from core.services.groups import GroupService
from utils.chatmember import extract_status_change
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class GroupManage(Plugin):
    def __init__(
        self,
        group_service: GroupService,
    ):
        self.type_handler = None
        self.group_service = group_service

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
