from typing import TYPE_CHECKING

from telegram.constants import ChatType
from telegram.ext import ApplicationHandlerStop

from gram_core.plugin import Plugin
from gram_core.plugin._handler import HandlerData
from gram_core.services.groups.services import GroupService
from gram_core.services.players import PlayersService

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class Ignore(Plugin):
    def __init__(
        self,
        players_service: PlayersService,
        group_service: GroupService,
    ):
        self.players_service = players_service
        self.group_service = group_service

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
        raise ApplicationHandlerStop
