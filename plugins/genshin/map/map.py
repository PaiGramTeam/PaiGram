from os import sep

from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackContext
from telegram.helpers import create_deep_linked_url

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
            region_name = None
            zoom = None
            if len(args) >= 2:
                region_name = args[1]
            if len(args) >= 3:
                zoom = args[2]
        else:
            logger.info(f"用户: {user.full_name} [{user.id}] 使用了 map 命令")
            await message.reply_text("请按以下格式发送指令`/map <资源名称> [区域名称] [地图缩放等级]`，或私聊派蒙发送 `/map list` 查看资源列表", parse_mode="Markdown")
            return
        if resource_name in ("list", "列表"):
            if filters.ChatType.GROUPS.filter(message):
                buttons = [[InlineKeyboardButton("点我私聊", url=create_deep_linked_url(context.bot.username))]]
                reply_message = await message.reply_text("请私聊派蒙使用该命令", reply_markup=InlineKeyboardMarkup(buttons))
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
                return
            logger.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 资源列表")
            text = self.map_helper.get_resource_list_mes()
            await message.reply_text(text)
            return
        logger.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 {resource_name}，区域 {region_name}，缩放 {zoom}")
        text, img_f = await self.map_helper.get_resource_map_mes(resource_name, region_name, zoom)
        if "不知道" in text or "没有找到" in text:
            await message.reply_text(text, parse_mode="Markdown")
            return
        img = Image.open(img_f)
        img_f.seek(0)
        if img.size[0] > 2048 or img.size[1] > 2048:
            await message.reply_document(img_f, caption=text)
        else:
            await message.reply_photo(img_f, caption=text)
