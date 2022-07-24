from os import sep

from PIL import Image
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters

from logger import Log
from utils.plugins.manager import listener_plugins_class
from plugins.base import BasePlugins, restricts
from plugins.errorhandler import conversation_error_handler
from service.map import MapHelper
from utils.base import PaimonContext


@listener_plugins_class()
class Map(BasePlugins):

    def __init__(self):
        self.init_resource_map = False
        self.map_helper = MapHelper()

    @classmethod
    def create_handlers(cls) -> list:
        map_res = cls()
        return [
            CommandHandler("map", map_res.command_start, block=False),
            MessageHandler(filters.Regex(r"^资源点查询(.*)"), map_res.command_start, block=True)
        ]

    async def init_point_list_and_map(self):
        Log.info("正在初始化地图资源节点")
        if not self.init_resource_map:
            await self.map_helper.init_point_list_and_map()
            self.init_resource_map = True

    @conversation_error_handler
    @restricts(restricts_time=20)
    async def command_start(self, update: Update, context: PaimonContext):
        message = update.message
        args = context.args
        user = update.effective_user
        if not self.init_resource_map:
            await self.init_point_list_and_map()
        await message.reply_chat_action(ChatAction.TYPING)
        if len(args) >= 1:
            resource_name = args[0]
        else:
            Log.info(f"用户: {user.full_name} [{user.id}] 使用了 map 命令")
            await message.reply_text("请输入要查找的资源，或私聊派蒙发送 `/map list` 查看资源列表", parse_mode="Markdown")
            return
        if resource_name in ("list", "列表"):
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text("请私聊派蒙使用该命令")
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
                return
            Log.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 资源列表")
            text = self.map_helper.get_resource_list_mes()
            await message.reply_text(text)
            return
        Log.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 {resource_name}")
        text = await self.map_helper.get_resource_map_mes(resource_name)
        if "不知道" in text or "没有找到" in text:
            await message.reply_text(text, parse_mode="Markdown")
            return
        img = Image.open(f"cache{sep}map.jpg")
        if img.size[0] > 2048 or img.size[1] > 2048:
            await message.reply_document(open(f"cache{sep}map.jpg", mode='rb+'), caption=text)
        else:
            await message.reply_photo(open(f"cache{sep}map.jpg", mode='rb+'), caption=text)
