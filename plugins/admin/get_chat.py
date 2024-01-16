import contextlib
import html
from typing import Tuple, Optional, TYPE_CHECKING

from telegram import ChatMemberAdministrator, ChatMemberOwner, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest, Forbidden

from core.basemodel import RegionEnum
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.groups.services import GroupService
from core.services.users.services import UserBanService
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Chat, ChatMember, Update
    from telegram.ext import ContextTypes


class GetChat(Plugin):
    def __init__(
        self,
        players_service: PlayersService,
        cookies_service: CookiesService,
        group_service: GroupService,
        user_ban_service: UserBanService,
    ):
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.group_service = group_service
        self.user_ban_service = user_ban_service

    @staticmethod
    async def parse_group_chat(chat: "Chat", admins: Tuple["ChatMember", ...], is_banned: bool) -> str:
        text = f"群 ID：<code>{chat.id}</code>\n群名称：<code>{chat.title}</code>\n"
        text += f"黑名单：<code>{'是' if is_banned else '否'}</code>\n"
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

    async def parse_private_chat(self, chat: "Chat", is_banned: bool) -> str:
        text = (
            f'<a href="tg://user?id={chat.id}">MENTION</a>\n'
            f"用户 ID：<code>{chat.id}</code>\n"
            f"用户名称：<code>{chat.full_name}</code>\n"
        )
        text += f"黑名单：<code>{'是' if is_banned else '否'}</code>\n"
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

    def get_chat_id(self, context: "ContextTypes.DEFAULT_TYPE") -> Optional[int]:
        args = self.get_args(context)
        if args and len(args) > 1 and args[0].isnumeric():
            return int(args[0])

    @staticmethod
    def gen_button(chat_id: int) -> "InlineKeyboardMarkup":
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "拉黑",
                        callback_data=f"block|add|{chat_id}",
                    ),
                    InlineKeyboardButton(
                        "取消拉黑",
                        callback_data=f"block|del|{chat_id}",
                    ),
                ],
            ]
        )

    @handler.command(command="get_chat", block=False, admin=True)
    async def get_chat_command(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        message = update.effective_message
        chat_id = self.get_chat_id(context)
        logger.info("用户 %s[%s] get_chat 命令请求 chat_id[%s]", user.full_name, user.id, chat_id)
        if not chat_id:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        if chat_id < 0:
            is_banned = await self.group_service.is_banned(chat_id)
        else:
            is_banned = await self.user_ban_service.is_banned(chat_id)
        try:
            chat = await self.get_chat(chat_id)
            if chat_id < 0:
                admins = await chat.get_administrators()
                text = await self.parse_group_chat(chat, admins, is_banned)
            else:
                text = await self.parse_private_chat(chat, is_banned)
            await message.reply_text(text, parse_mode="HTML", reply_markup=self.gen_button(chat_id))
        except (BadRequest, Forbidden) as exc:
            logger.warning("通过 id 获取会话信息失败，API 返回：%s", str(exc))
            text = f"会话 ID：<code>{chat_id}</code>\n"
            text += f"黑名单：<code>{'是' if is_banned else '否'}</code>\n"
            await message.reply_text(text, parse_mode="HTML", reply_markup=self.gen_button(chat_id))

    @handler.command(command="leave_chat", block=False, admin=True)
    async def leave_chat(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        message = update.effective_message
        chat_id = self.get_chat_id(context)
        logger.info("用户 %s[%s] leave_chat 命令请求 chat_id[%s]", user.full_name, user.id, chat_id)
        if not chat_id:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            with contextlib.suppress(BadRequest, Forbidden):
                chat = await context.bot.get_chat(chat_id)
                await message.reply_text(f"正在尝试退出群 {chat.title}[{chat.id}]")
            await context.bot.leave_chat(chat_id)
        except (BadRequest, Forbidden) as exc:
            await message.reply_text(f"退出 chat_id[{chat_id}] 发生错误！ 错误信息为 {str(exc)}")
            return
        await message.reply_text(f"退出 chat_id[{chat_id}] 成功！")
