from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.plugin import Plugin, handler
from core.services.game.services import GameMaterialService
from metadata.shortname import roleToName
from utils.log import logger

__all__ = ("MaterialPlugin",)


class MaterialPlugin(Plugin):
    """角色培养素材查询"""

    KEYBOARD = [[InlineKeyboardButton(text="查看角色培养素材列表并查询", switch_inline_query_current_chat="查看角色培养素材列表并查询")]]

    def __init__(self, game_material_service: GameMaterialService = None):
        self.game_material_service = game_material_service

    @handler(CommandHandler, command="material", block=False)
    @handler(MessageHandler, filters=filters.Regex("^角色培养素材查询(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = self.get_args(context)
        if len(args) >= 1:
            character_name = args[0]
        else:
            reply_message = await message.reply_text(
                "请回复你要查询的培养素材的角色名", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        character_name = roleToName(character_name)
        url = await self.game_material_service.get_material(character_name)
        if not url:
            reply_message = await message.reply_text(
                f"没有找到 {character_name} 的培养素材", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        logger.info("用户 %s[%s] 查询角色培养素材命令请求 || 参数 %s", user.full_name, user.id, character_name)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        file_path = await self.download_resource(url, return_path=True)
        caption = "From 米游社 " f"查看 [原图]({url})"
        await message.reply_photo(
            photo=open(file_path, "rb"),
            caption=caption,
            filename=f"{character_name}.png",
            allow_sending_without_reply=True,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
