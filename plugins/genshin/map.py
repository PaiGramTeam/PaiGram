from io import BytesIO

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackContext

from core.baseplugin import BasePlugin
from core.plugin import handler, Plugin
from modules.apihelper.client.components.map import MapHelper, MapException
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class Map(Plugin, BasePlugin):
    """资源点查询"""

    def __init__(self):
        self.map_helper = MapHelper()

    @handler(CommandHandler, command="map", block=False)
    @handler(MessageHandler, filters=filters.Regex("^资源点查询(.*)"), block=False)
    @error_callable
    @restricts(restricts_time=20)
    async def command_start(self, update: Update, context: CallbackContext):
        message = update.effective_message
        args = context.args
        user = update.effective_user
        if not self.map_helper.query_map:
            await self.map_helper.refresh_query_map()
        if not self.map_helper.label_count:
            await self.map_helper.refresh_label_count()
        await message.reply_chat_action(ChatAction.TYPING)
        if len(args) >= 1:
            resource_name = args[0]
        else:
            logger.info(f"用户: {user.full_name} [{user.id}] 使用了 map 命令")
            await message.reply_text("请指定要查找的资源名称。", parse_mode="Markdown")
            return
        logger.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 {resource_name}")
        if resource_name not in self.map_helper.query_map:
            await message.reply_text("没有找到该资源。", parse_mode="Markdown")
            return
        caption = f"派蒙一共找到 {resource_name} 的 {self.map_helper.get_label_count('2', resource_name)} 个位置点\n* 数据来源于米游社wiki"
        try:
            data = await self.map_helper.get_map(resource_name, "2")
            if len(data) > (1024 * 1024):
                data = BytesIO(data)
                data.name = "map.jpg"
                await message.reply_document(data, caption=caption)
            else:
                await message.reply_photo(data, caption=caption)
        except MapException as e:
            await message.reply_text(e.message, parse_mode="Markdown")
