from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import filters, CommandHandler, MessageHandler, CallbackContext

from apps.template.services import TemplateService
from apps.wiki.services import WikiService
from logger import Log
from metadata.shortname import weaponToName
from plugins.base import BasePlugins
from utils.apps.inject import inject
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file
from utils.plugins.manager import listener_plugins_class


@listener_plugins_class()
class Weapon(BasePlugins):
    """武器查询"""

    KEYBOARD = [[InlineKeyboardButton(text="查看武器列表并查询", switch_inline_query_current_chat="查看武器列表并查询")]]

    @inject
    def __init__(self, template_service: TemplateService, wiki_service: WikiService):
        self.wiki_service = wiki_service
        self.template_service = template_service

    @classmethod
    def create_handlers(cls) -> list:
        weapon = cls()
        return [
            CommandHandler("weapon", weapon.command_start, block=False),
            MessageHandler(filters.Regex("^武器查询(.*)"), weapon.command_start, block=False)
        ]

    @error_callable
    @restricts()
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = get_all_args(context)
        if len(args) >= 1:
            weapon_name = args[0]
        else:
            reply_message = await message.reply_text("请回复你要查询的武器",
                                                     reply_markup=InlineKeyboardMarkup(self.KEYBOARD))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        weapon_name = weaponToName(weapon_name)
        weapons_list = await self.wiki_service.get_weapons_list()
        for weapon in weapons_list:
            if weapon["name"] == weapon_name:
                weapon_data = weapon
                break
        else:
            reply_message = await message.reply_text(f"没有找到 {weapon_name}",
                                                     reply_markup=InlineKeyboardMarkup(self.KEYBOARD))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        Log.info(f"用户 {user.full_name}[{user.id}] 查询武器命令请求 || 参数 {weapon_name}")
        await message.reply_chat_action(ChatAction.TYPING)

        async def input_template_data(_weapon_data):
            _template_data = {
                "weapon_name": _weapon_data["name"],
                "weapon_info_type_img": await url_to_file(_weapon_data["type"]["icon"]),
                "progression_secondary_stat_value": _weapon_data["secondary"]["max"],
                "progression_secondary_stat_name": _weapon_data["secondary"]["name"],
                "weapon_info_source_img": await url_to_file(_weapon_data["source_img"]),
                "progression_base_atk": _weapon_data["atk"]["max"],
                "weapon_info_source_list": [],
                "special_ability_name": _weapon_data["passive_ability"]["name"],
                "special_ability_info": _weapon_data["passive_ability"]["description"],
            }
            _template_data["weapon_info_source_list"].append(
                await url_to_file(_weapon_data["materials"]["ascension"]["icon"])
            )
            _template_data["weapon_info_source_list"].append(
                await url_to_file(_weapon_data["materials"]["elite"]["icon"])
            )
            _template_data["weapon_info_source_list"].append(
                await url_to_file(_weapon_data["materials"]["monster"]["icon"])
            )
            return _template_data

        template_data = await input_template_data(weapon_data)
        png_data = await self.template_service.render('genshin/weapon', "weapon.html", template_data,
                                                      {"width": 540, "height": 540})
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(png_data, filename=f"{template_data['weapon_name']}.png",
                                  allow_sending_without_reply=True)
