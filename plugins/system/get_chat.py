from typing import List

from telegram import Update, Chat, ChatMember, ChatMemberOwner, ChatMemberAdministrator
from telegram.error import BadRequest, Forbidden
from telegram.ext import CommandHandler, CallbackContext

from core.plugin import Plugin, handler
from utils.bot import get_all_args
from utils.decorators.admins import bot_admins_rights_check
from utils.log import logger


class GetChat(Plugin):
    @staticmethod
    def parse_chat(chat: Chat, admins: List[ChatMember]) -> str:
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
            if chat_id > 0:
                await message.reply_text("参数错误，请指定群 id ！")
                return
        except ValueError:
            await message.reply_text("参数错误，请指定群 id ！")
            return
        try:
            chat = await message.get_bot().get_chat(args[0])
            admins = await chat.get_administrators()
            await message.reply_text(self.parse_chat(chat, admins), parse_mode="HTML")
        except (BadRequest, Forbidden) as exc:
            await message.reply_text(f"获取群信息失败，API 返回：{exc}")
            return
