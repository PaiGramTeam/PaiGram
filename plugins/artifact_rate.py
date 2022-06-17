from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from model.apihelper.artifact import ArtifactORCRate
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler
from service import BaseService


class ArtifactRate(BasePlugins):
    """
    圣遗物评分
    """
    STAR_KEYBOARD = [[InlineKeyboardButton("1", switch_inline_query_current_chat="artifact_star|1"),
                      InlineKeyboardButton("2", switch_inline_query_current_chat="artifact_star|1"),
                      InlineKeyboardButton("3", switch_inline_query_current_chat="artifact_star|1"),
                      InlineKeyboardButton("4", switch_inline_query_current_chat="artifact_star|1"),
                      InlineKeyboardButton("5", switch_inline_query_current_chat="artifact_star|1")]]

    LEVEL_KEYBOARD = [[InlineKeyboardButton("1", switch_inline_query_current_chat="artifact_level|1"),
                       InlineKeyboardButton("2", switch_inline_query_current_chat="artifact_level|2"),
                       InlineKeyboardButton("3", switch_inline_query_current_chat="artifact_level|3"),
                       InlineKeyboardButton("4", switch_inline_query_current_chat="artifact_level|4"),
                       InlineKeyboardButton("5", switch_inline_query_current_chat="artifact_level|5")],
                      [InlineKeyboardButton("6", switch_inline_query_current_chat="artifact_level|6"),
                       InlineKeyboardButton("7", switch_inline_query_current_chat="artifact_level|7"),
                       InlineKeyboardButton("8", switch_inline_query_current_chat="artifact_level|8"),
                       InlineKeyboardButton("9", switch_inline_query_current_chat="artifact_level|9"),
                       InlineKeyboardButton("10", switch_inline_query_current_chat="artifact_level|0")],
                      [InlineKeyboardButton("11", switch_inline_query_current_chat="artifact_level|11"),
                       InlineKeyboardButton("12", switch_inline_query_current_chat="artifact_level|12"),
                       InlineKeyboardButton("13", switch_inline_query_current_chat="artifact_level|13"),
                       InlineKeyboardButton("14", switch_inline_query_current_chat="artifact_level|14"),
                       InlineKeyboardButton("15", switch_inline_query_current_chat="artifact_level|15")],
                      [InlineKeyboardButton("16", switch_inline_query_current_chat="artifact_level|16"),
                       InlineKeyboardButton("17", switch_inline_query_current_chat="artifact_level|17"),
                       InlineKeyboardButton("18", switch_inline_query_current_chat="artifact_level|18"),
                       InlineKeyboardButton("19", switch_inline_query_current_chat="artifact_level|19"),
                       InlineKeyboardButton("20", switch_inline_query_current_chat="artifact_level|20")]
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
        if message.photo is None:
            return await message.reply_text("图呢？\n"
                                            "*请命令将与截图一起发送")
        photo_file = await message.photo[0].get_file()
        photo_byte = await photo_file.download_as_bytearray()
        artifact_attr_req = await self.artifact_rate.get_artifact_attr(photo_byte)
        if artifact_attr_req.status_code != 200:
            return await message.reply_text("API请求错误")
        artifact_attr = artifact_attr_req.json()
        if 'star' not in artifact_attr:
            await message.reply_text("无法识别圣遗物星级，请回复数字（1-5）：",
                                     reply_markup=InlineKeyboardMarkup(self.STAR_KEYBOARD))
            return
        if 'level' not in artifact_attr:
            await message.reply_text("无法识别圣遗物等级，请回复数字（1-20）：",
                                     reply_markup=InlineKeyboardMarkup(self.LEVEL_KEYBOARD))
        reply_message = await message.reply_text("识图成功！\n"
                                                 "正在评分中...")
        rate_text = await self.get_rate(artifact_attr)
        await reply_message.edit_message_text(rate_text)
        return ConversationHandler.END

    async def get_star(self, update: Update, context: CallbackContext) -> int:
        pass
