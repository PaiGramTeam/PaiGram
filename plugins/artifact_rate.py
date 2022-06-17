from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler

from logger import Log
from model.apihelper.artifact import ArtifactORCRate
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler
from service import BaseService


class ArtifactRate(BasePlugins):
    COMMAND_RESULT = 0

    """
    圣遗物评分
    """
    STAR_KEYBOARD = [[InlineKeyboardButton("1", callback_data="artifact_orc_rate_data|star|1"),
                      InlineKeyboardButton("2", callback_data="artifact_orc_rate_data|star|2"),
                      InlineKeyboardButton("3", callback_data="artifact_orc_rate_data|star|3"),
                      InlineKeyboardButton("4", callback_data="artifact_orc_rate_data|star|4"),
                      InlineKeyboardButton("5", callback_data="artifact_orc_rate_data|level|5")]]

    LEVEL_KEYBOARD = [[InlineKeyboardButton("1", callback_data="artifact_orc_rate_data|level|1"),
                       InlineKeyboardButton("2", callback_data="artifact_orc_rate_data|level|2"),
                       InlineKeyboardButton("3", callback_data="artifact_orc_rate_data|level|3"),
                       InlineKeyboardButton("4", callback_data="artifact_orc_rate_data|level|4"),
                       InlineKeyboardButton("5", callback_data="artifact_orc_rate_data|level|5")],
                      [InlineKeyboardButton("6", callback_data="artifact_orc_rate_data|level|6"),
                       InlineKeyboardButton("7", callback_data="artifact_orc_rate_data|level|7"),
                       InlineKeyboardButton("8", callback_data="artifact_orc_rate_data|level|8"),
                       InlineKeyboardButton("9", callback_data="artifact_orc_rate_data|level|9"),
                       InlineKeyboardButton("10", callback_data="artifact_orc_rate_data|level|0")],
                      [InlineKeyboardButton("11", callback_data="artifact_orc_rate_data|level|11"),
                       InlineKeyboardButton("12", callback_data="artifact_orc_rate_data|level|12"),
                       InlineKeyboardButton("13", callback_data="artifact_orc_rate_data|level|13"),
                       InlineKeyboardButton("14", callback_data="artifact_orc_rate_data|level|14"),
                       InlineKeyboardButton("15", callback_data="artifact_orc_rate_data|level|15")],
                      [InlineKeyboardButton("16", callback_data="artifact_orc_rate_data|level|16"),
                       InlineKeyboardButton("17", callback_data="artifact_orc_rate_data|level|17"),
                       InlineKeyboardButton("18", callback_data="artifact_orc_rate_data|level|18"),
                       InlineKeyboardButton("19", callback_data="artifact_orc_rate_data|level|19"),
                       InlineKeyboardButton("20", callback_data="artifact_orc_rate_data|level|20")]
                      ]

    def __init__(self, service: BaseService):
        super().__init__(service)
        self.artifact_rate = ArtifactORCRate()

    async def get_rate(self, artifact_attr: dict) -> str:
        rate_result = await self.artifact_rate.rate_artifact(artifact_attr)
        if rate_result.status_code != 200:
            return "API请求错误"
        artifact_attr = rate_result.json()
        format_result = f'圣遗物评分结果：\n' \
                        f'主属性：{artifact_attr["main_item"]["name"]}\n' \
                        f'{self.artifact_rate.get_format_sub_item(artifact_attr)}' \
                        f'`------------------------------`\n' \
                        f'总分：{rate_result["total_percent"]}\n' \
                        f'主词条：{rate_result["main_percent"]}\n' \
                        f'副词条：{rate_result["sub_percent"]}\n' \
                        f'`------------------------------`\n' \
                        f'{self.artifact_rate.get_yiyan(rate_result["total_percent"])}\n' \
                        f'评分、识图均来自 genshin.pub'
        return format_result

    @conversation_error_handler
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        message = update.message
        user = update.effective_user
        Log.info(f"用户 {user.full_name}[{user.id}] 绑定账号命令请求")
        context.user_data["artifact_attr"] = None
        if message.photo is None:
            return await message.reply_text("图呢？\n"
                                            "*请命令将与截图一起发送")
        photo_file = await message.photo[0].get_file()
        photo_byte = await photo_file.download_as_bytearray()
        artifact_attr_req = await self.artifact_rate.get_artifact_attr(photo_byte)
        if artifact_attr_req.status_code != 200:
            return await message.reply_text("API请求错误")
        artifact_attr = artifact_attr_req.json()
        context.user_data["artifact_attr"] = artifact_attr
        if artifact_attr.get("star") is None:
            await message.reply_text("无法识别圣遗物星级，请点击数字",
                                     reply_markup=InlineKeyboardMarkup(self.STAR_KEYBOARD))
            return self.COMMAND_RESULT
        if artifact_attr.get("level") is None:
            await message.reply_text("无法识别圣遗物等级，请点击数字",
                                     reply_markup=InlineKeyboardMarkup(self.LEVEL_KEYBOARD))
            return self.COMMAND_RESULT
        reply_message = await message.reply_text("识图成功！\n"
                                                 "正在评分中...")
        rate_text = await self.get_rate(artifact_attr)
        await reply_message.edit_message_text(rate_text)
        return ConversationHandler.END

    @conversation_error_handler
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        if artifact_attr := context.user_data.get("artifact_attr"):
            return ConversationHandler.END

        def get_callback_data(callback_query_data: str) -> tuple[str, int]:
            _data = callback_query_data.split("|")
            _key_name = _data[2]
            try:
                _value = int(_data[2])
            except ValueError:
                _value = -1
            return _key_name, _value

        query = update.callback_query
        await query.answer()
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
            await query.edit_message_text("无法识别圣遗物等级，请点击数字",
                                          reply_markup=InlineKeyboardMarkup(self.LEVEL_KEYBOARD))
            return self.COMMAND_RESULT
        if artifact_attr.get("star") is None:
            await query.edit_message_text("无法识别圣遗物星级，请点击数字",
                                          reply_markup=InlineKeyboardMarkup(self.STAR_KEYBOARD))
            return self.COMMAND_RESULT
        await query.edit_message_text("正在评分中...")
        rate_text = await self.get_rate(artifact_attr)
        await query.edit_message_text(rate_text)
        return ConversationHandler.END
