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


class Pokedex(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)

    async def command_start(self, update: Update, _: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = message.text.split(" ")
        search_command = re.search(r"^角色查询(.*)", message.text)
        keyboard = [
            [
                InlineKeyboardButton(text="查看角色图鉴列表并查询", switch_inline_query_current_chat="查看角色图鉴列表并查询")
            ]
        ]
        if search_command:
            role_name = search_command[1]
            if role_name == "":
                await message.reply_text("请回复你要查询的图鉴的角色名", reply_markup=InlineKeyboardMarkup(keyboard))
                return
        elif len(args) >= 2:
            role_name = args[1]
        else:
            await message.reply_text("请回复你要查询的图鉴的角色名", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        if role_name not in ["风主", "岩主", "雷主"]:
            role_name = roleToName(role_name)
        file_path = Path(f"resources{os.sep}genshin{os.sep}pokedex{os.sep}{role_name}.png")
        if (not role_name) or (not os.path.isfile(file_path)):
            await message.reply_text(f"没有找到 {role_name} 的图鉴",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
            return

        Log.info(f"用户 {user.full_name}[{user.id}] 查询角色图鉴命令请求 || 参数 {role_name}")

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(photo=open(file_path, "rb"),
                                  filename=f"{role_name}.png",
                                  allow_sending_without_reply=True)
