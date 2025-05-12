import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.dependence.assets.impl.genshin import AssetsService
from core.plugin import Plugin, handler
from core.services.template.services import TemplateService
from metadata.shortname import roleToName
from modules.apihelper.client.components.remote import Remote
from modules.material.talent import TalentMaterials
from utils.log import logger

__all__ = ("MaterialPlugin",)


class MaterialPlugin(Plugin):
    """角色培养素材查询"""

    KEYBOARD = [
        [
            InlineKeyboardButton(
                text="查看角色培养素材列表并查询", switch_inline_query_current_chat="查看角色培养素材列表并查询"
            )
        ]
    ]

    def __init__(
        self,
        template_service: TemplateService,
        assets_service: AssetsService,
    ):
        self.roles_material = {}
        self.assets_service = assets_service
        self.template_service = template_service

    async def initialize(self):
        await self._refresh()

    async def _refresh(self):
        self.roles_material = await Remote.get_remote_material()

    async def _parse_material(self, data: dict, character_name: str, talent_level: str) -> dict:
        data = data["data"]
        if character_name not in data.keys():
            return {}
        character = self.assets_service.avatar.get_by_name(character_name)
        level_up_material = self.assets_service.material.get_by_name(data[character_name]["level_up_materials"])
        ascension_material = self.assets_service.material.get_by_name(data[character_name]["ascension_materials"])
        local_material = self.assets_service.material.get_by_name(data[character_name]["materials"][0])
        enemy_material = self.assets_service.material.get_by_name(data[character_name]["materials"][1])
        level_up_materials = [
            {
                "num": 46,
                "rarity": level_up_material.rank,
                "icon": self.assets_service.material.icon(level_up_material.id).as_uri(),
                "name": data[character_name]["level_up_materials"],
            },
            {
                "num": 419,
                "rarity": 4,
                "icon": self.assets_service.material.icon(104003).as_uri(),
                "name": "大英雄的经验",
            },
            {
                "num": 1,
                "rarity": 2,
                "icon": self.assets_service.material.icon(int(ascension_material.id) - 3).as_uri(),
                "name": self.assets_service.material.get_by_id(int(ascension_material.id) - 3).name,
            },
            {
                "num": 9,
                "rarity": 3,
                "icon": self.assets_service.material.icon(int(ascension_material.id) - 2).as_uri(),
                "name": self.assets_service.material.get_by_id(int(ascension_material.id) - 2).name,
            },
            {
                "num": 9,
                "rarity": 4,
                "icon": self.assets_service.material.icon(int(ascension_material.id) - 1).as_uri(),
                "name": self.assets_service.material.get_by_id(int(ascension_material.id) - 1).name,
            },
            {
                "num": 6,
                "rarity": 5,
                "icon": self.assets_service.material.icon(ascension_material.id).as_uri(),
                "name": self.assets_service.material.get_by_id(ascension_material.id).name,
            },
            {
                "num": 168,
                "rarity": local_material.rank,
                "icon": self.assets_service.material.icon(local_material.id).as_uri(),
                "name": local_material.name,
            },
            {
                "num": 18,
                "rarity": enemy_material.rank,
                "icon": self.assets_service.material.icon(enemy_material.id).as_uri(),
                "name": enemy_material.name,
            },
            {
                "num": 30,
                "rarity": self.assets_service.material.get_by_id(int(enemy_material.id) + 1).rank,
                "icon": self.assets_service.material.icon(int(enemy_material.id) + 1).as_uri(),
                "name": self.assets_service.material.get_by_id(int(enemy_material.id) + 1).name,
            },
            {
                "num": 36,
                "rarity": self.assets_service.material.get_by_id(int(enemy_material.id) + 2).rank,
                "icon": self.assets_service.material.icon(int(enemy_material.id) + 2).as_uri(),
                "name": self.assets_service.material.get_by_id(int(enemy_material.id) + 2).name,
            },
        ]
        talent_book = self.assets_service.material.get_by_name(f"「{data[character_name]['talent'][0]}」的教导")
        weekly_talent_material = self.assets_service.material.get_by_name(data[character_name]["talent"][1])
        talent_materials = [
            {
                "num": 9,
                "rarity": talent_book.rank,
                "icon": self.assets_service.material.icon(talent_book.id).as_uri(),
                "name": talent_book.name,
            },
            {
                "num": 63,
                "rarity": self.assets_service.material.get_by_id(int(talent_book.id) + 1).rank,
                "icon": self.assets_service.material.icon(int(talent_book.id) + 1).as_uri(),
                "name": self.assets_service.material.get_by_id(int(talent_book.id) + 1).name,
            },
            {
                "num": 114,
                "rarity": self.assets_service.material.get_by_id(int(talent_book.id) + 2).rank,
                "icon": self.assets_service.material.icon(int(talent_book.id) + 2).as_uri(),
                "name": self.assets_service.material.get_by_id(int(talent_book.id) + 2).name,
            },
            {
                "num": 18,
                "rarity": enemy_material.rank,
                "icon": self.assets_service.material.icon(enemy_material.id).as_uri(),
                "name": enemy_material.name,
            },
            {
                "num": 66,
                "rarity": self.assets_service.material.get_by_id(int(enemy_material.id) + 1).rank,
                "icon": self.assets_service.material.icon(int(enemy_material.id) + 1).as_uri(),
                "name": self.assets_service.material.get_by_id(int(enemy_material.id) + 1).name,
            },
            {
                "num": 93,
                "rarity": self.assets_service.material.get_by_id(int(enemy_material.id) + 2).rank,
                "icon": self.assets_service.material.icon(int(enemy_material.id) + 2).as_uri(),
                "name": self.assets_service.material.get_by_id(int(enemy_material.id) + 2).name,
            },
            {
                "num": 3,
                "rarity": 5,
                "icon": self.assets_service.material.icon(104319).as_uri(),
                "name": "智识之冕",
            },
            {
                "num": 18,
                "rarity": weekly_talent_material.rank,
                "icon": self.assets_service.material.icon(weekly_talent_material.id).as_uri(),
                "name": weekly_talent_material.name,
            },
        ]

        return {
            "character": {
                "element": character.element.value,
                "image": self.assets_service.avatar.gacha(character_name).as_uri(),
                "name": character_name,
                "association": self.assets_service.avatar.get_by_name(character_name).association.name,
            },
            "level_up_materials": level_up_materials,
            "talent_materials": talent_materials,
            "talent_level": talent_level,
            "talent_amount": TalentMaterials(list(map(int, talent_level.split("/")))).cal_materials(),
        }

    async def render(self, character_name: str, talent_amount: str):
        if not self.roles_material:
            await self._refresh()
        data = await self._parse_material(self.roles_material, character_name, talent_amount)
        if not data:
            return
        return await self.template_service.render(
            "genshin/material/roles_material.jinja2",
            data,
            {"width": 960, "height": 1460},
            full_page=True,
            ttl=7 * 24 * 60 * 60,
        )

    @staticmethod
    def _is_valid(string: str):
        """
        判断字符串是否符合`8/9/10`的格式并保证每个数字都在[1，10]
        """
        return bool(
            re.match(r"^\d+/\d+/\d+$", string)
            and all(1 <= int(num) <= 10 for num in string.split("/"))
            and string != "1/1/1"
            and string != "10/10/10"
        )

    @handler(CommandHandler, command="material", block=False)
    @handler(MessageHandler, filters=filters.Regex("^角色培养素材查询(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        args = self.get_args(context)
        if len(args) >= 1:
            character_name = args[0]
            material_count = "8/8/8"
            if len(args) >= 2 and self._is_valid(args[1]):
                material_count = args[1]
        else:
            reply_message = await message.reply_text(
                "请回复你要查询的培养素材的角色名", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        character_name = roleToName(character_name)
        self.log_user(update, logger.info, "查询角色培养素材命令请求 || 参数 %s", character_name)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        result = await self.render(character_name, material_count)
        if not result:
            reply_message = await message.reply_text(
                f"没有找到 {character_name} 的培养素材", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        await result.reply_photo(message)
