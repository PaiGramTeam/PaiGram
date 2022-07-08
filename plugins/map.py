from os import sep

from PIL import Image
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters

from logger import Log
from manager import listener_plugins_class
from plugins.base import BasePlugins, restricts
from plugins.errorhandler import conversation_error_handler
from service.map import get_resource_map_mes, get_resource_list_mes, init_point_list_and_map
from utils.base import PaimonContext

init_resource_map = False


async def inquire_resource_list(message):
    """ 资源列表 """
    global init_resource_map
    if not init_resource_map:
        await init_point_list_and_map()
        init_resource_map = True
    text = get_resource_list_mes()
    await message.reply_text(text)


@listener_plugins_class()
class Map(BasePlugins):
    @classmethod
    def create_handlers(cls) -> list:
        map = cls()
        return [
            CommandHandler("map", map.command_start, block=False),
            MessageHandler(filters.Regex(r"^资源点查询(.*)"), map.command_start, block=True)
        ]

    @conversation_error_handler
    @restricts()
    async def command_start(self, update: Update, context: PaimonContext) -> None:
        """ 资源点查询 """
        message = update.message
        args = context.args
        user = update.effective_user
        global init_resource_map
        if not init_resource_map:
            await init_point_list_and_map()
            init_resource_map = True
        await message.reply_chat_action(ChatAction.TYPING)
        if len(args) >= 1:
            resource_name = args[0]
        else:
            Log.info(f"用户: {user.full_name} [{user.id}] 使用了 map 命令")
            return await message.reply_text("请输入要查找的资源，或发送 `/map list` 查看资源列表", parse_mode="Markdown")
        if resource_name in ("list", "列表"):
            Log.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 资源列表")
            return await inquire_resource_list(message)
        Log.info(f"用户: {user.full_name} [{user.id}] 使用 map 命令查询了 {resource_name}")
        text = await get_resource_map_mes(resource_name)
        if "不知道" in text:
            return await message.reply_text(text, parse_mode="Markdown")
        img = Image.open(f"temp{sep}map.jpg")
        if img.size[0] > 2048 or img.size[1] > 2048:
            await message.reply_document(open(f"temp{sep}map.jpg", mode='rb+'), caption=text)
        else:
            await message.reply_photo(open(f"temp{sep}map.jpg", mode='rb+'), caption=text)
