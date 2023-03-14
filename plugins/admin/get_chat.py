import html
from typing import Tuple

from telegram import Chat, ChatMember, ChatMemberAdministrator, ChatMemberOwner, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, CommandHandler

from core.basemodel import RegionEnum
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from utils.log import logger


class GetChat(Plugin):
    def __init__(
        self,
        players_service: PlayersService,
        cookies_service: CookiesService,
    ):
        self.cookies_service = cookies_service
        self.players_service = players_service

    @staticmethod
    async def parse_group_chat(chat: Chat, admins: Tuple[ChatMember]) -> str:
        text = f"群 ID：<code>{chat.id}</code>\n群名称：<code>{chat.title}</code>\n"
        if chat.username:
            text += f"群用户名：@{chat.username}\n"
        if chat.description:
            text += f"群简介：<code>{html.escape(chat.description)}</code>\n"
        if admins:
            for admin in admins:
                text += f'<a href="tg://user?id={admin.user.id}">{html.escape(admin.user.full_name)}</a> '
                if isinstance(admin, ChatMemberAdministrator):
                    text += "C" if admin.can_change_info else "_"
                    text += "D" if admin.can_delete_messages else "_"
                    text += "R" if admin.can_restrict_members else "_"
                    text += "I" if admin.can_invite_users else "_"
                    text += "T" if admin.can_manage_topics else "_"
                    text += "P" if admin.can_pin_messages else "_"
                    text += "V" if admin.can_manage_video_chats else "_"
                    text += "N" if admin.can_promote_members else "_"
                    text += "A" if admin.is_anonymous else "_"
                elif isinstance(admin, ChatMemberOwner):
                    text += "创建者"
                text += "\n"
        return text

    async def parse_private_chat(self, chat: Chat) -> str:
        text = (
            f'<a href="tg://user?id={chat.id}">MENTION</a>\n'
            f"用户 ID：<code>{chat.id}</code>\n"
            f"用户名称：<code>{chat.full_name}</code>\n"
        )
        if chat.username:
            text += f"用户名：@{chat.username}\n"
        player_info = await self.players_service.get_player(chat.id)
        if player_info is not None:
            if player_info.region == RegionEnum.HYPERION:
                text += "米游社绑定："
            else:
                text += "原神绑定："
            cookies_info = await self.cookies_service.get(chat.id, player_info.account_id, player_info.region)
            if cookies_info is None:
                temp = "UID 绑定"
            else:
                temp = "Cookie 绑定"
            text += f"<code>{temp}</code>\n游戏 ID：<code>{player_info.player_id}</code>"
        return text

    @handler(CommandHandler, command="get_chat", block=False, admin=True)
    async def get_chat_command(self, update: Update, context: CallbackContext):
        user = update.effective_user
        logger.info("用户 %s[%s] get_chat 命令请求", user.full_name, user.id)
        message = update.effective_message
        args = self.get_args(context)
        if not args:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            chat_id = int(args[0])
        except ValueError:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            chat = await self.get_chat(args[0])
            if chat_id < 0:
                admins = await chat.get_administrators() if chat_id < 0 else None
                text = await self.parse_group_chat(chat, admins)
            else:
                text = await self.parse_private_chat(chat)
            await message.reply_text(text, parse_mode="HTML")
        except (BadRequest, Forbidden) as exc:
            await message.reply_text(f"通过 id 获取会话信息失败，API 返回：{exc.message}")
