import contextlib
import html
from typing import List

from telegram import (Chat, ChatMember, ChatMemberAdministrator,
                      ChatMemberOwner, Update)
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, CommandHandler

from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.sign import SignServices
from core.user import UserService
from core.user.error import UserNotFoundError
from modules.gacha_log.log import GachaLog
from utils.bot import get_args, get_chat as get_chat_with_cache
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import get_genshin_client
from utils.log import logger
from utils.models.base import RegionEnum


class GetChat(Plugin):
    def __init__(
        self,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
        sign_service: SignServices = None,
    ):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.sign_service = sign_service
        self.gacha_log = GachaLog()

    async def parse_group_chat(self, chat: Chat, admins: List[ChatMember]) -> str:
        text = f"群 ID：<code>{chat.id}</code>\n群名称：<code>{chat.title}</code>\n"
        if chat.username:
            text += f"群用户名：@{chat.username}\n"
        sign_info = await self.sign_service.get_by_chat_id(chat.id)
        if sign_info:
            text += f"自动签到推送人数：<code>{len(sign_info)}</code>\n"
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
        try:
            user_info = await self.user_service.get_user_by_id(chat.id)
        except UserNotFoundError:
            user_info = None
        if user_info is not None:
            if user_info.region == RegionEnum.HYPERION:
                text += "米游社绑定："
                uid = user_info.yuanshen_uid
            else:
                text += "原神绑定："
                uid = user_info.genshin_uid
            temp = "Cookie 绑定"
            try:
                await get_genshin_client(chat.id)
            except CookiesNotFoundError:
                temp = "UID 绑定"
            text += f"<code>{temp}</code>\n游戏 ID：<code>{uid}</code>"
            sign_info = await self.sign_service.get_by_user_id(chat.id)
            if sign_info is not None:
                text += (
                    f"\n自动签到：已开启"
                    f"\n推送会话：<code>{sign_info.chat_id}</code>"
                    f"\n开启时间：<code>{sign_info.time_created}</code>"
                    f"\n更新时间：<code>{sign_info.time_updated}</code>"
                    f"\n签到状态：<code>{sign_info.status.name}</code>"
                )
            else:
                text += "\n自动签到：未开启"
            with contextlib.suppress(Exception):
                gacha_log, status = await self.gacha_log.load_history_info(str(chat.id), str(uid))
                if status:
                    text += "\n抽卡记录："
                    for key, value in gacha_log.item_list.items():
                        text += f"\n   - {key}：{len(value)} 条"
                    text += f"\n   - 最后更新：{gacha_log.update_time.strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    text += "\n抽卡记录：<code>未导入</code>"
        return text

    @handler(CommandHandler, command="get_chat", block=False)
    @bot_admins_rights_check
    async def get_chat(self, update: Update, context: CallbackContext):
        user = update.effective_user
        logger.info("用户 %s[%s] get_chat 命令请求", user.full_name, user.id)
        message = update.effective_message
        args = get_args(context)
        if not args:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            chat_id = int(args[0])
        except ValueError:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            chat = await get_chat_with_cache(args[0])
            if chat_id < 0:
                admins = await chat.get_administrators() if chat_id < 0 else None
                text = await self.parse_group_chat(chat, admins)
            else:
                text = await self.parse_private_chat(chat)
            await message.reply_text(text, parse_mode="HTML")
        except (BadRequest, Forbidden) as exc:
            await message.reply_text(f"通过 id 获取会话信息失败，API 返回：{exc.message}")
