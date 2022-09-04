from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, CallbackContext
from telegram.ext import MessageHandler, filters

from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.wiki.services import WikiService
from metadata.shortname import weaponToName
from models.wiki.base import SCRAPE_HOST
from models.wiki.weapon import Weapon
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file
from utils.log import logger


class WeaponPlugin(Plugin, BasePlugin):
    """武器查询"""

    KEYBOARD = [[
        InlineKeyboardButton(text="查看武器列表并查询", switch_inline_query_current_chat="查看武器列表并查询")
    ]]

    def __init__(self, template_service: TemplateService = None, wiki_service: WikiService = None):
        self.wiki_service = wiki_service
        self.template_service = template_service

    @handler(CommandHandler, command="help", block=False)
    @handler(MessageHandler, filters=filters.Regex("^武器查询(.*)"), block=False)
    @error_callable
    @restricts()
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
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
            if weapon.name == weapon_name:
                weapon_data = weapon
                break
        else:
            reply_message = await message.reply_text(f"没有找到 {weapon_name}",
                                                     reply_markup=InlineKeyboardMarkup(self.KEYBOARD))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 查询武器命令请求 || 参数 {weapon_name}")
        await message.reply_chat_action(ChatAction.TYPING)

        async def input_template_data(_weapon_data: Weapon):
            if weapon.rarity > 2:
                bonus = _weapon_data.stats[-1].bonus
                if '%' in bonus:
                    bonus = str(round(float(bonus.rstrip('%')))) + '%'
                else:
                    bonus = str(round(float(bonus)))
                _template_data = {
                    "weapon_name": _weapon_data.name,
                    "weapon_info_type_img": await url_to_file(_weapon_data.weapon_type.icon_url()),
                    "progression_secondary_stat_value": bonus,
                    "progression_secondary_stat_name": _weapon_data.attribute.type.value,
                    "weapon_info_source_img": await url_to_file(_weapon_data.icon.icon),
                    "weapon_info_max_level": _weapon_data.stats[-1].level,
                    "progression_base_atk": round(_weapon_data.stats[-1].ATK),
                    "weapon_info_source_list": [
                        await url_to_file(str(SCRAPE_HOST.join(f'/img/{mid}.png')))
                        for mid in _weapon_data.ascension[-3:]
                    ],
                    "special_ability_name": _weapon_data.affix.name,
                    "special_ability_info": _weapon_data.affix.description[0],
                }
            else:
                _template_data = {
                    "weapon_name": _weapon_data.name,
                    "weapon_info_type_img": await url_to_file(_weapon_data.weapon_type.icon_url()),
                    "progression_secondary_stat_value": ' ',
                    "progression_secondary_stat_name": '无其它属性加成',
                    "weapon_info_source_img": await url_to_file(_weapon_data.icon.icon),
                    "weapon_info_max_level": _weapon_data.stats[-1].level,
                    "progression_base_atk": round(_weapon_data.stats[-1].ATK),
                    "weapon_info_source_list": [
                        await url_to_file(str(SCRAPE_HOST.join(f'/img/{mid}.png')))
                        for mid in _weapon_data.ascension[-3:]
                    ],
                    "special_ability_name": '',
                    "special_ability_info": _weapon_data.description,
                }
            return _template_data

        template_data = await input_template_data(weapon_data)
        png_data = await self.template_service.render('genshin/weapon', "weapon.html", template_data,
                                                      {"width": 540, "height": 540})
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(png_data, filename=f"{template_data['weapon_name']}.png",
                                  allow_sending_without_reply=True)
