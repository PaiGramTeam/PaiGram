from typing import List

from telegram import Update, Chat, ChatMember, ChatMemberOwner, ChatMemberAdministrator
from telegram.error import BadRequest, Forbidden
from telegram.ext import CommandHandler, CallbackContext

from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.user import UserService
from core.user.error import UserNotFoundError
from modules.apihelper.gacha_log import GachaLog
from utils.bot import get_all_args
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import get_genshin_client
from utils.log import logger
from utils.models.base import RegionEnum


class GetChat(Plugin):
    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None):
        self.cookies_service = cookies_service
        self.user_service = user_service

    @staticmethod
    def parse_group_chat(chat: Chat, admins: List[ChatMember]) -> str:
        text = f"群 ID：<code>{chat.id}</code>\n" \
               f"群名称：<code>{chat.title}</code>\n"
        if chat.username:
            text += f"群用户名：<code>{chat.username}</code>\n"
        if chat.description:
            text += f"群简介：<code>{chat.description}</code>\n"
        if admins:
            for admin in admins:
                text += f"<a href=\"tg://user?id={admin.user.id}\">{admin.user.full_name}</a> "
                if isinstance(admin, ChatMemberAdministrator):
                    text += "C" if admin.can_change_info else "_"
                    text += "D" if admin.can_delete_messages else "_"
                    text += "R" if admin.can_restrict_members else "_"
                    text += "I" if admin.can_invite_users else "_"
                    text += "P" if admin.can_pin_messages else "_"
                    text += "V" if admin.can_manage_video_chats else "_"
                    text += "N" if admin.can_promote_members else "_"
                    text += "A" if admin.is_anonymous else "_"
                elif isinstance(admin, ChatMemberOwner):
                    text += "创建者"
                text += "\n"
        return text

    async def parse_private_chat(self, chat: Chat) -> str:
        text = f"<a href=\"tg://user?id={chat.id}\">MENTION</a>\n" \
               f"用户 ID：<code>{chat.id}</code>\n" \
               f"用户名称：<code>{chat.full_name}</code>\n"
        if chat.username:
            text += f"用户名：@{chat.username}\n"
        try:
            user_info = await self.user_service.get_user_by_id(chat.id)
        except UserNotFoundError:
            user_info = None
        if user_info is not None:
            text += "米游社绑定：" if user_info.region == RegionEnum.HYPERION else "HOYOLAB 绑定："
            temp = "Cookie 绑定"
            try:
                await get_genshin_client(chat.id)
            except CookiesNotFoundError:
                temp = "UID 绑定"
            uid = user_info.genshin_uid or user_info.yuanshen_uid
            text += f"<code>{temp}</code>\n" \
                    f"游戏 ID：<code>{uid}</code>"
            gacha_log, status = await GachaLog.load_history_info(str(chat.id), str(uid))
            if status:
                text += f"\n抽卡记录："
                for key, value in gacha_log.item_list.items():
                    text += f"\n   - {key}：{len(value)} 条"
            else:
                text += f"\n抽卡记录：<code>未导入</code>"
        return text

    @handler(CommandHandler, command="get_chat", block=False)
    @bot_admins_rights_check
    async def get_chat(self, update: Update, context: CallbackContext):
        user = update.effective_user
        logger.info(f"用户 {user.full_name}[{user.id}] get_chat 命令请求")
        message = update.effective_message
        args = get_all_args(context)
        if not args:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            chat_id = int(args[0])
        except ValueError:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            chat = await message.get_bot().get_chat(args[0])
            if chat_id < 0:
                admins = await chat.get_administrators() if chat_id < 0 else None
                text = self.parse_group_chat(chat, admins)
            else:
                text = await self.parse_private_chat(chat)
            await message.reply_text(text, parse_mode="HTML")
        except (BadRequest, Forbidden) as exc:
            await message.reply_text(f"通过 id 获取会话信息失败，API 返回：{exc}")
            return
