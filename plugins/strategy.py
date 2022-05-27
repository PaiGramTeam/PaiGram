import os
import re
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext

from logger import Log
from plugins.base import BasePlugins
from service import BaseService
from metadata.shortname import roleToName


class Strategy(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)

    async def command_start(self, update: Update, _: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = message.text.split(" ")
        search_command = re.search(r"^角色攻略查询(.*)", message.text)
        keyboard = [
            [
                InlineKeyboardButton(text="查看角色攻略列表并查询", switch_inline_query_current_chat="查看角色攻略列表并查询")
            ]
        ]
        if search_command:
            role_name = roleToName(search_command[1])
            if role_name == "":
                await message.reply_text("请回复你要查询的攻略的角色名", reply_markup=InlineKeyboardMarkup(keyboard))
                return
        elif len(args) >= 2:
            role_name = roleToName(args[1])
        else:
            await message.reply_text("请回复你要查询的攻略的角色名", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        file_path = Path(f"resources{os.sep}genshin{os.sep}strategy{os.sep}{role_name}.jpg")
        if (not role_name) or (not os.path.isfile(file_path)):
            await message.reply_text(f"没有找到 {role_name} 的攻略",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
            return

        Log.info(f"用户 {user.full_name}[{user.id}] 查询角色攻略命令请求 || 参数 {role_name}")

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(photo=open(file_path, "rb"),
                                  filename=f"{role_name}.png",
                                  allow_sending_without_reply=True)
