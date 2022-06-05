import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, filters

from logger import Log
from model.helpers import url_to_file
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler
from service import BaseService
from metadata.shortname import weaponToName
from metadata.metadata import metadat


class Weapon(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)

    @conversation_error_handler
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = context.args
        search_command = re.search(r'^武器查询(.*)', message.text)
        keyboard = [
            [
                InlineKeyboardButton(text="查看武器列表并查询", switch_inline_query_current_chat="查看武器列表并查询")
            ]
        ]
        if search_command:
            weapon_name = search_command[1]
            if weapon_name == "":
                reply_message = await message.reply_text("请回复你要查询的武器", reply_markup=InlineKeyboardMarkup(keyboard))
                if filters.ChatType.GROUPS.filter(reply_message):
                    self._add_delete_message_job(context, message.chat_id, message.message_id)
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
                return
        elif len(args) >= 2:
            weapon_name = args[1]
        else:
            reply_message = await message.reply_text("请回复你要查询的武器", reply_markup=InlineKeyboardMarkup(keyboard))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        weapon_name = weaponToName(weapon_name)
        weapon_data = None
        for weapon in metadat.weapons:
            if weapon["Name"] == weapon_name:
                weapon_data = weapon
        if weapon_data is None:
            reply_message = await message.reply_text(f"没有找到 {weapon_name}",
                                                     reply_markup=InlineKeyboardMarkup(keyboard))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return

        Log.info(f"用户 {user.full_name}[{user.id}] 查询武器命令请求 || 参数 {weapon_name}")
        await message.reply_chat_action(ChatAction.TYPING)

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
