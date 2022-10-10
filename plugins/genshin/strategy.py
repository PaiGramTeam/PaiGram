from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.constants import ChatAction
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext
from telegram.ext import MessageHandler, filters

from core.baseplugin import BasePlugin
from core.game.services import GameStrategyService
from core.plugin import Plugin, handler
from metadata.shortname import roleToName
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file
from utils.log import logger


class StrategyPlugin(Plugin, BasePlugin):
    """角色攻略查询"""

    KEYBOARD = [[InlineKeyboardButton(text="查看角色攻略列表并查询", switch_inline_query_current_chat="查看角色攻略列表并查询")]]

    def __init__(self, game_strategy_service: GameStrategyService = None):
        self.game_strategy_service = game_strategy_service

    @handler(CommandHandler, command="strategy", block=False)
    @handler(MessageHandler, filters=filters.Regex("^角色攻略查询(.*)"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = get_all_args(context)
        if len(args) >= 1:
            character_name = args[0]
        else:
            reply_message = await message.reply_text("请回复你要查询的攻略的角色名", reply_markup=InlineKeyboardMarkup(self.KEYBOARD))
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        character_name = roleToName(character_name)
        url = await self.game_strategy_service.get_strategy(character_name)
        if url == "":
            reply_message = await message.reply_text(
                f"没有找到 {character_name} 的攻略", reply_markup=InlineKeyboardMarkup(self.KEYBOARD)
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 查询角色攻略命令请求 || 参数 {character_name}")
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        file_path = await url_to_file(url, return_path=True)
        caption = "From 米游社 西风驿站  " f"查看 [原图]({url})"
        await message.reply_photo(
            photo=open(file_path, "rb"),
            caption=caption,
            filename=f"{character_name}.png",
            allow_sending_without_reply=True,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
