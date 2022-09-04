from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, File
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, \
    filters
from telegram.helpers import escape_markdown

from core.baseplugin import BasePlugin
from core.plugin import Plugin, conversation, handler
from models.apihelper.artifact import ArtifactOcrRate, get_comment, get_format_sub_item
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger

COMMAND_RESULT = 1


class ArtifactRate(Plugin.Conversation, BasePlugin):
    """圣遗物评分"""

    STAR_KEYBOARD = [[
        InlineKeyboardButton(
            f"{i}", callback_data=f"artifact_ocr_rate_data|star|{i}") for i in range(1, 6)
    ]]

    LEVEL_KEYBOARD = [[
        InlineKeyboardButton(
            f"{i * 5 + j}", callback_data=f"artifact_ocr_rate_data|level|{i * 5 + j}") for j in range(1, 6)
    ] for i in range(0, 4)]

    def __init__(self):
        self.artifact_rate = ArtifactOcrRate()

    @classmethod
    def create_handlers(cls) -> list:
        artifact_rate = cls()
        return [
            ConversationHandler(
                entry_points=[CommandHandler('artifact_rate', artifact_rate.command_start),
                              MessageHandler(filters.Regex(r"^圣遗物评分(.*)"), artifact_rate.command_start),
                              MessageHandler(filters.CaptionRegex(r"^圣遗物评分(.*)"), artifact_rate.command_start)],
                states={
                    artifact_rate.COMMAND_RESULT: [CallbackQueryHandler(artifact_rate.command_result)]
                },
                fallbacks=[CommandHandler('cancel', artifact_rate.cancel)]
            )
        ]

    async def get_rate(self, artifact_attr: dict) -> str:
        rate_result_req = await self.artifact_rate.rate_artifact(artifact_attr)
        if rate_result_req.status_code != 200:
            if rate_result_req.status_code == 400:
                artifact_attr = rate_result_req.json()
                return artifact_attr.get("message", "API请求错误")
            return "API请求错误"
        rate_result = rate_result_req.json()
        return "*圣遗物评分结果*\n" \
               f"主属性：{escape_markdown(artifact_attr['main_item']['name'], version=2)}\n" \
               f"{escape_markdown(get_format_sub_item(artifact_attr), version=2)}" \
               f'`--------------------`\n' \
               f"总分：{escape_markdown(rate_result['total_percent'], version=2)}\n" \
               f"主词条：{escape_markdown(rate_result['main_percent'], version=2)}\n" \
               f"副词条：{escape_markdown(rate_result['sub_percent'], version=2)}\n" \
               f'`--------------------`\n' \
               f"{escape_markdown(get_comment(rate_result['total_percent']), version=2)}\n" \
               "_评分、识图均来自 genshin\\.pub_"

    @conversation.entry_point
    @handler.command(command='artifact_rate', filters=filters.ChatType.PRIVATE, block=True)
    @handler.message(filters=filters.Regex(r"^圣遗物评分(.*)"), block=True)
    @handler.message(filters=filters.CaptionRegex(r"^圣遗物评分(.*)"), block=True)
    @error_callable
    @restricts(return_data=ConversationHandler.END)
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        logger.info(f"用户 {user.full_name}[{user.id}] 圣遗物评分命令请求")
        context.user_data["artifact_attr"] = None
        photo_file: Optional[File] = None
        if message is None:
            return ConversationHandler.END
        else:
            if message.reply_to_message is None:
                message_data = message
            else:
                message_data = message.reply_to_message
            if message_data.photo is not None and len(message_data.photo) >= 1:
                photo_file = await message_data.photo[-1].get_file()  # 草 居然第一张是预览图我人都麻了
            elif message_data.document is not None:
                document = message_data.document
                if "image" not in document.mime_type:
                    await message.reply_text("错误的图片类型")
                    return ConversationHandler.END
                if document.file_size / 1024 / 1024 >= 5:
                    await message.reply_text("图片太大啦")
                    return ConversationHandler.END
                photo_file = await document.get_file()
        if photo_file is None:
            await message.reply_text("图呢？")
            return ConversationHandler.END
        photo_byte = await photo_file.download_as_bytearray()
        artifact_attr_req = await self.artifact_rate.get_artifact_attr(photo_byte)
        if artifact_attr_req.status_code != 200:
            if artifact_attr_req.status_code == 400:
                artifact_attr = artifact_attr_req.json()
                await message.reply_text(artifact_attr.get("message", "API请求错误"))
                return ConversationHandler.END
            await message.reply_text("API请求错误")
            return ConversationHandler.END
        artifact_attr = artifact_attr_req.json()
        context.user_data["artifact_attr"] = artifact_attr
        if artifact_attr.get("star") is None:
            await message.reply_text("无法识别圣遗物星级，请选择圣遗物星级",
                                     reply_markup=InlineKeyboardMarkup(self.STAR_KEYBOARD))
            return self.COMMAND_RESULT
        if artifact_attr.get("level") is None:
            await message.reply_text("无法识别圣遗物等级，请选择圣遗物等级",
                                     reply_markup=InlineKeyboardMarkup(self.LEVEL_KEYBOARD))
            return self.COMMAND_RESULT
        reply_message = await message.reply_text("识图成功！\n"
                                                 "正在评分中...")
        rate_text = await self.get_rate(artifact_attr)
        await reply_message.edit_text(rate_text, parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    @conversation.state(state=COMMAND_RESULT)
    @handler.callback_query()
    @error_callable
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        artifact_attr = context.user_data.get("artifact_attr")
        await query.answer()
        if artifact_attr is None:
            await query.edit_message_text("数据错误")
            return ConversationHandler.END

        def get_callback_data(callback_query_data: str) -> tuple[str, int]:
            _data = callback_query_data.split("|")
            _key_name = _data[1]
            try:
                _value = int(_data[2])
            except ValueError:
                _value = -1
            return _key_name, _value

        await query.message.reply_chat_action(ChatAction.TYPING)
        key_name, value = get_callback_data(query.data)
        if key_name == "level":
            artifact_attr["level"] = value
        elif key_name == "star":
            artifact_attr["star"] = value
        else:
            await query.edit_message_text("数据错误")
            return ConversationHandler.END
        if artifact_attr.get("level") is None:
            await query.edit_message_text("无法识别圣遗物等级，请选择圣遗物等级",
                                          reply_markup=InlineKeyboardMarkup(self.LEVEL_KEYBOARD))
            return self.COMMAND_RESULT
        if artifact_attr.get("star") is None:
            await query.edit_message_text("无法识别圣遗物星级，请选择圣遗物星级",
                                          reply_markup=InlineKeyboardMarkup(self.STAR_KEYBOARD))
            return self.COMMAND_RESULT
        await query.edit_message_text("正在评分中...")
        rate_text = await self.get_rate(artifact_attr)
        await query.edit_message_text(rate_text, parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END
