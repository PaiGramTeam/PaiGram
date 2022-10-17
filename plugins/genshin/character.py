from ast import Call
from distutils.log import Log
from click import command
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.wiki.services import WikiService
from metadata.genshin import honey_id_to_game_id
from metadata.shortname import weaponToName
from metadata.shortname import roleToName
from modules.wiki.weapon import Weapon
from modules.wiki.character import Character
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file
from utils.log import logger


class CharacterPlugin(Plugin, BasePlugin):
    """角色查询"""

    KEYBOARD = [[InlineKeyboardButton(text="查看角色列表并查询", switch_inline_query_current_chat="查看角色列表并查询")]]

    def __init__(
        self,
        template_service: TemplateService = None,
        wiki_service: WikiService = None,
        assets_service: AssetsService = None,
    ):
        self.wiki_service = wiki_service
        self.template_service = template_service
        self.assets_service = assets_service

    @handler(CommandHandler, command="character", block=False)
    @handler(MessageHandler, filters=filters.Regex("^角色查询(.*)"), block=False)
    @error_callable
    @restricts()
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = get_all_args(context)
        if len(args) >= 1:
            character_name = args[0]
        else:
            reply_message = await message.reply_text("请回复你要查询的角色", reply_markup=InlineKeyboardMarkup(self.KEYBOARD))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        character_name = roleToName(character_name)
        logger.info(f"用户 {user.full_name}[{user.id}] 查询角色命令请求 || 参数 character_name={character_name}")
        character_list = await self.wiki_service.get_characters_list()
        for character in character_list:
            if character.name == character_name:
                character_data = character
                break
        else:
            reply_message = await message.reply_text(
                f"没有找到 {character_name}", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        await message.reply_chat_action(ChatAction.TYPING)

        async def input_template_data(_character_data: Character):
            _template_data = {
                "character_name": _character_data.name,
                "cv": _character_data.cn_cv,
            }
            return _template_data

        template_data = await input_template_data(character_data)
        png_data = await self.template_service.render(
            "genshin/character", "character.html", template_data, {"width": 540, "height": 540}
        )
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(
            png_data, filename=f"{template_data['character_name']}.png", allow_sending_without_reply=True
        )
