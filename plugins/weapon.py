import os
import time
from uuid import uuid4
import re
import aiofiles

from jinja2 import Environment, PackageLoader
from playwright.async_api import async_playwright, ViewportSize

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext

from logger import Log
from model.helpers import url_to_file
from plugins.base import BasePlugins
from service import BaseService
from metadata.metadata import metadat


class Weapon(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)

    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = message.text.split(" ")
        search_command = re.search(r'^武器查询(.*)', message.text)
        keyboard = [
            [
                InlineKeyboardButton(text="查看武器列表并查询", switch_inline_query_current_chat="查看武器列表并查询")
            ]
        ]
        if search_command:
            weapon_name = search_command[1]
            if weapon_name == "":
                await message.reply_text("请回复你要查询的武器", reply_markup=InlineKeyboardMarkup(keyboard))
                return
        elif len(args) >= 2:
            weapon_name = args[1]
        else:
            await message.reply_text("请回复你要查询的武器", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        weapon_data = None
        for weapon in metadat.weapons:
            if weapon["Name"] == weapon_name:
                weapon_data = weapon
        if weapon_data is None:
            await message.reply_text(f"没有找到 {weapon_name}",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
            return

        Log.info(f"用户 {user.full_name}[{user.id}] 查询武器命令请求 || 参数 {weapon_name}")

        await message.reply_chat_action(ChatAction.FIND_LOCATION)

        async def input_template_data(_weapon_data):
            _template_data = {
                "weapon_name": _weapon_data["Name"],
                "weapon_info_type_img": await url_to_file(_weapon_data["Type"]),
                "progression_secondary_stat_value": _weapon_data["SubStatValue"],
                "progression_secondary_stat_name": _weapon_data["SubStat"],
                "weapon_info_source_img": await url_to_file(_weapon_data["Source"]),
                "progression_base_atk": _weapon_data["ATK"],
                "weapon_info_source_list": [],
                "special_ability_name": _weapon_data["Passive"],
                "special_ability_info": _weapon_data["PassiveDescription"]["Lv1"],
            }
            _template_data["weapon_info_source_list"].append(
                await url_to_file(_weapon_data["Ascension"]["Source"])
            )
            _template_data["weapon_info_source_list"].append(
                await url_to_file(_weapon_data["Elite"]["Source"])
            )
            _template_data["weapon_info_source_list"].append(
                await url_to_file(_weapon_data["Monster"]["Source"])
            )
            return _template_data

        template_data = await input_template_data(weapon_data)
        png_data = await self.service.template.render('genshin/weapon', "weapon.html", template_data,
                                                      {"width": 540, "height": 540})
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(png_data, filename=f"{template_data['weapon_name']}.png",
                                  allow_sending_without_reply=True)
