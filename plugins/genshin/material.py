from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (CallbackContext, CommandHandler, ConversationHandler,
                          MessageHandler, filters)

from core.baseplugin import BasePlugin
from core.game.services import GameMaterialService
from core.plugin import Plugin, handler
from metadata.shortname import roleToName
from utils.bot import get_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file
from utils.log import logger


class Material(Plugin, BasePlugin):
    """角色培养素材查询"""

    KEYBOARD = [[InlineKeyboardButton(text="查看角色培养素材列表并查询", switch_inline_query_current_chat="查看角色培养素材列表并查询")]]

    def __init__(self, game_material_service: GameMaterialService = None):
        self.game_material_service = game_material_service

    @handler(CommandHandler, command="material", block=False)
    @handler(MessageHandler, filters=filters.Regex("^角色培养素材查询(.*)"), block=False)
    @restricts(return_data=ConversationHandler.END)
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = get_args(context)
        if len(args) >= 1:
            character_name = args[0]
        else:
            reply_message = await message.reply_text(
                "请回复你要查询的培养素材的角色名", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        character_name = roleToName(character_name)
        url = await self.game_material_service.get_material(character_name)
        if not url:
            reply_message = await message.reply_text(
                f"没有找到 {character_name} 的培养素材", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 查询角色培养素材命令请求 || 参数 {character_name}")
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        file_path = await url_to_file(url, return_path=True)
        caption = "From 米游社 " f"查看 [原图]({url})"
        await message.reply_photo(
            photo=open(file_path, "rb"),
            caption=caption,
            filename=f"{character_name}.png",
            allow_sending_without_reply=True,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
