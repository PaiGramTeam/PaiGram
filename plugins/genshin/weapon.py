from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.dependence.assets import AssetsCouldNotFound, AssetsService
from core.plugin import Plugin, handler
from core.services.search.models import WeaponEntry
from core.services.search.services import SearchServices
from core.services.template.services import TemplateService
from core.services.wiki.services import WikiService
from metadata.genshin import honey_id_to_game_id
from metadata.shortname import weaponToName, weapons as _weapons_data
from modules.wiki.weapon import Weapon
from utils.log import logger


class WeaponPlugin(Plugin):
    """武器查询"""

    KEYBOARD = [[InlineKeyboardButton(text="查看武器列表并查询", switch_inline_query_current_chat="查看武器列表并查询")]]

    def __init__(
        self,
        template_service: TemplateService = None,
        wiki_service: WikiService = None,
        assets_service: AssetsService = None,
        search_service: SearchServices = None,
    ):
        self.wiki_service = wiki_service
        self.template_service = template_service
        self.assets_service = assets_service
        self.search_service = search_service

    @handler(CommandHandler, command="weapon", block=False)
    @handler(MessageHandler, filters=filters.Regex("^武器查询(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = self.get_args(context)
        if len(args) >= 1:
            weapon_name = args[0]
        else:
            reply_message = await message.reply_text("请回复你要查询的武器", reply_markup=InlineKeyboardMarkup(self.KEYBOARD))
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        weapon_name = weaponToName(weapon_name)
        logger.info("用户 %s[%s] 查询角色攻略命令请求 weapon_name[%s]", user.full_name, user.id, weapon_name)
        weapons_list = await self.wiki_service.get_weapons_list()
        for weapon in weapons_list:
            if weapon.name == weapon_name:
                weapon_data = weapon
                break
        else:
            reply_message = await message.reply_text(
                f"没有找到 {weapon_name}", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        await message.reply_chat_action(ChatAction.TYPING)

        async def input_template_data(_weapon_data: Weapon):
            if weapon.rarity > 2:
                bonus = _weapon_data.stats[-1].bonus
                if "%" in bonus:
                    bonus = str(round(float(bonus.rstrip("%")))) + "%"
                else:
                    bonus = str(round(float(bonus)))
                _template_data = {
                    "weapon_name": _weapon_data.name,
                    "weapon_rarity": _weapon_data.rarity,
                    "weapon_info_type_img": await self.download_resource(_weapon_data.weapon_type.icon_url()),
                    "progression_secondary_stat_value": bonus,
                    "progression_secondary_stat_name": _weapon_data.attribute.type.value,
                    "weapon_info_source_img": (
                        await self.assets_service.weapon(honey_id_to_game_id(_weapon_data.id, "weapon")).icon()
                    ).as_uri(),
                    "weapon_info_max_level": _weapon_data.stats[-1].level,
                    "progression_base_atk": round(_weapon_data.stats[-1].ATK),
                    "weapon_info_source_list": [
                        (await self.assets_service.material(honey_id_to_game_id(mid, "material")).icon()).as_uri()
                        for mid in _weapon_data.ascension[-3:]
                    ],
                    "special_ability_name": _weapon_data.affix.name,
                    "special_ability_info": _weapon_data.affix.description[0],
                    "weapon_description": _weapon_data.description,
                }
            else:
                _template_data = {
                    "weapon_name": _weapon_data.name,
                    "weapon_rarity": _weapon_data.rarity,
                    "weapon_info_type_img": await self.download_resource(_weapon_data.weapon_type.icon_url()),
                    "progression_secondary_stat_value": " ",
                    "progression_secondary_stat_name": "无其它属性加成",
                    "weapon_info_source_img": (
                        await self.assets_service.weapon(honey_id_to_game_id(_weapon_data.id, "weapon")).icon()
                    ).as_uri(),
                    "weapon_info_max_level": _weapon_data.stats[-1].level,
                    "progression_base_atk": round(_weapon_data.stats[-1].ATK),
                    "weapon_info_source_list": [
                        (await self.assets_service.material(honey_id_to_game_id(mid, "material")).icon()).as_uri()
                        for mid in _weapon_data.ascension[-3:]
                    ],
                    "special_ability_name": "",
                    "special_ability_info": "",
                    "weapon_description": _weapon_data.description,
                }
            return _template_data

        try:
            template_data = await input_template_data(weapon_data)
        except AssetsCouldNotFound as exc:
            logger.warning("%s weapon_name[%s]", exc.message, weapon_name)
            reply_message = await message.reply_text(f"数据库中没有找到 {weapon_name}")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        png_data = await self.template_service.render(
            "genshin/weapon/weapon.jinja2", template_data, {"width": 540, "height": 540}, ttl=31 * 24 * 60 * 60
        )
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        reply_photo = await png_data.reply_photo(
            message,
            filename=f"{template_data['weapon_name']}.png",
            allow_sending_without_reply=True,
        )
        if reply_photo.photo:
            description = weapon_data.story
            if description:
                photo_file_id = reply_photo.photo[0].file_id
                tags = _weapons_data.get(weapon_name)
                entry = WeaponEntry(
                    key=f"plugin:weapon:{weapon_name}",
                    title=weapon_name,
                    description=description,
                    tags=tags,
                    photo_file_id=photo_file_id,
                )
                await self.search_service.add_entry(entry)
