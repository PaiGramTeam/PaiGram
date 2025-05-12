from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, filters

from core.dependence.assets.impl.genshin import AssetsCouldNotFound, AssetsService
from core.dependence.assets.impl.models.genshin.weapon import Weapon
from core.plugin import Plugin, handler
from core.services.search.models import WeaponEntry
from core.services.search.services import SearchServices
from core.services.template.services import TemplateService
from metadata.shortname import weaponToName, weapons as _weapons_data
from utils.log import logger


class WeaponPlugin(Plugin):
    """武器查询"""

    KEYBOARD = [
        [InlineKeyboardButton(text="查看武器列表并查询", switch_inline_query_current_chat="查看武器列表并查询")]
    ]

    def __init__(
        self,
        template_service: TemplateService = None,
        assets_service: AssetsService = None,
        search_service: SearchServices = None,
    ):
        self.template_service = template_service
        self.assets_service = assets_service
        self.search_service = search_service

    @handler.command(command="weapon", block=False)
    @handler.message(filters=filters.Regex("^武器查询(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        args = self.get_args(context)
        if len(args) >= 1:
            weapon_name = args[0]
        else:
            reply_message = await message.reply_text(
                "请回复你要查询的武器", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        weapon_name = weaponToName(weapon_name)
        self.log_user(update, logger.info, "查询角色攻略命令请求 weapon_name[%s]", weapon_name)
        weapon_data = self.assets_service.weapon.get_by_name(weapon_name)
        if not weapon_data:
            reply_message = await message.reply_text(
                f"没有找到 {weapon_name}", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        await message.reply_chat_action(ChatAction.TYPING)

        async def input_template_data(_weapon_data: Weapon):
            if _weapon_data.rarity > 2:
                bonus = _weapon_data.stats[-1].bonus
                if "%" in bonus:
                    bonus = str(round(float(bonus.rstrip("%")))) + "%"
                else:
                    bonus = str(round(float(bonus)))
                _template_data = {
                    "weapon_name": _weapon_data.name,
                    "weapon_rarity": _weapon_data.rarity,
                    "weapon_info_type_img": _weapon_data.weapon_type.name,
                    "progression_secondary_stat_value": bonus,
                    "progression_secondary_stat_name": _weapon_data.attribute.type.value,
                    "weapon_info_source_img": self.assets_service.weapon.icon(_weapon_data.id).as_uri(),
                    "weapon_info_max_level": _weapon_data.stats[-1].level,
                    "progression_base_atk": round(_weapon_data.stats[-1].ATK),
                    "weapon_info_source_list": [
                        self.assets_service.material.icon(mid).as_uri() for mid in _weapon_data.ascension[-3:]
                    ],
                    "special_ability_name": _weapon_data.affix.name,
                    "special_ability_info": _weapon_data.affix.description[0],
                    "weapon_description": _weapon_data.description,
                }
            else:
                _template_data = {
                    "weapon_name": _weapon_data.name,
                    "weapon_rarity": _weapon_data.rarity,
                    "weapon_info_type_img": _weapon_data.weapon_type.name,
                    "progression_secondary_stat_value": " ",
                    "progression_secondary_stat_name": "无其它属性加成",
                    "weapon_info_source_img": self.assets_service.weapon.icon(_weapon_data.id).as_uri(),
                    "weapon_info_max_level": _weapon_data.stats[-1].level,
                    "progression_base_atk": round(_weapon_data.stats[-1].ATK),
                    "weapon_info_source_list": [
                        self.assets_service.material.icon(mid).as_uri() for mid in _weapon_data.ascension[-3:]
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
