import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters

from logger import Log
from metadata.shortname import roleToName
from model.helpers import url_to_file
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler


class Strategy(BasePlugins):
    """
    角色攻略查询
    """

    @conversation_error_handler
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = context.args
        search_command = re.search(r"^角色攻略查询(.*)", message.text)
        keyboard = [
            [
                InlineKeyboardButton(text="查看角色攻略列表并查询", switch_inline_query_current_chat="查看角色攻略列表并查询")
            ]
        ]
        await update.message.reply_chat_action(ChatAction.TYPING)
        role_name = ""
        if search_command:
            role_name = roleToName(search_command[1])
            if role_name == "":
                reply_message = await message.reply_text("请回复你要查询的攻略的角色名",
                                                         reply_markup=InlineKeyboardMarkup(keyboard))
                if filters.ChatType.GROUPS.filter(reply_message):
                    self._add_delete_message_job(context, message.chat_id, message.message_id)
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
                return
        elif args is not None:
            if len(args) >= 1:
                role_name = roleToName(args[0])
        else:
            reply_message = await message.reply_text("请回复你要查询的攻略的角色名",
                                                     reply_markup=InlineKeyboardMarkup(keyboard))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        url = await self.service.get_game_info.get_characters_cultivation_atlas(role_name)
        if url == "":
            reply_message = await message.reply_text(f"没有找到 {role_name} 的攻略",
                                                     reply_markup=InlineKeyboardMarkup(keyboard))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return

        Log.info(f"用户 {user.full_name}[{user.id}] 查询角色攻略命令请求 || 参数 {role_name}")

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        file_path = await url_to_file(url, "")
        caption = "Form 米游社 西风驿站  " \
                  f"查看 [原图]({url})"
        await message.reply_photo(photo=open(file_path, "rb"), caption=caption, filename=f"{role_name}.png",
                                  allow_sending_without_reply=True, parse_mode=ParseMode.MARKDOWN_V2)
