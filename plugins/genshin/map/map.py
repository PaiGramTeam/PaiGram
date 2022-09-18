from os import sep

from PIL import Image
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackContext

from core.baseplugin import BasePlugin
from core.plugin import handler, Plugin
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger
from .model import MapHelper


class Map(Plugin, BasePlugin):
    """支持资源点查询"""

    def __init__(self):
        self.init_resource_map = False
        self.map_helper = MapHelper()

    async def init_point_list_and_map(self):
        logger.info("正在初始化地图资源节点")
        if not self.init_resource_map:
            await self.map_helper.init_point_list_and_map()
            self.init_resource_map = True

    @handler(CommandHandler, command="map", block=False)
    @handler(MessageHandler, filters=filters.Regex("^资源点查询(.*)"), block=False)
    @error_callable
    @restricts(restricts_time=20)
    async def command_start(self, update: Update, context: CallbackContext):
        message = update.effective_message
        args = context.args
        user = update.effective_user
        if not self.init_resource_map:
            await self.init_point_list_and_map()
        await message.reply_chat_action(ChatAction.TYPING)
        if len(args) >= 1:
            resource_name = args[0]
        else:
            logger.info(f"用户: {user.full_name} [{user.id}] 使用了 map 命令")
            await message.reply_text("请输入要查找的资源，或私聊派蒙发送 `/map list` 查看资源列表", parse_mode="Markdown")
            return
        if resource_name in ("list", "列表"):
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text("请私聊派蒙使用该命令")
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
                return
            logger.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 资源列表")
            text = self.map_helper.get_resource_list_mes()
            await message.reply_text(text)
            return
        logger.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 {resource_name}")
        text = await self.map_helper.get_resource_map_mes(resource_name)
        if "不知道" in text or "没有找到" in text:
            await message.reply_text(text, parse_mode="Markdown")
            return
        img = Image.open(f"cache{sep}map.jpg")
        if img.size[0] > 2048 or img.size[1] > 2048:
            await message.reply_document(open(f"cache{sep}map.jpg", mode='rb+'), caption=text)
        else:
            await message.reply_photo(open(f"cache{sep}map.jpg", mode='rb+'), caption=text)
