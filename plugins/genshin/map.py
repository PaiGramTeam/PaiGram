from io import BytesIO
from typing import Union, Optional, List, Tuple

from telegram import Update, Message, InputMediaDocument, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.config import config
from core.plugin import handler, Plugin
from modules.apihelper.client.components.map import MapHelper, MapException
from utils.decorators.admins import bot_admins_rights_check
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class Map(Plugin, BasePlugin):
    """资源点查询"""

    def __init__(self, redis: RedisDB = None):
        self.cache = redis.client
        self.cache_photo_key = "plugin:map:photo:"
        self.cache_doc_key = "plugin:map:doc:"
        self.map_helper = MapHelper()
        self.temp_photo_path = "resources/img/map.png"
        self.temp_photo = None

    async def get_photo_cache(self, map_id: Union[str, int], name: str) -> Optional[str]:
        if file_id := await self.cache.get(f"{self.cache_photo_key}{map_id}:{name}"):
            return file_id.decode("utf-8")
        return None

    async def get_doc_cache(self, map_id: Union[str, int], name: str) -> Optional[str]:
        if file_id := await self.cache.get(f"{self.cache_doc_key}{map_id}:{name}"):
            return file_id.decode("utf-8")
        return None

    async def set_photo_cache(self, map_id: Union[str, int], name: str, file_id: str) -> None:
        await self.cache.set(f"{self.cache_photo_key}{map_id}:{name}", file_id)

    async def set_doc_cache(self, map_id: Union[str, int], name: str, file_id: str) -> None:
        await self.cache.set(f"{self.cache_doc_key}{map_id}:{name}", file_id)

    async def clear_cache(self) -> None:
        for i in await self.cache.keys(f"{self.cache_photo_key}*"):
            await self.cache.delete(i)
        for i in await self.cache.keys(f"{self.cache_doc_key}*"):
            await self.cache.delete(i)

    async def edit_media(self, message: Message, map_id: str, name: str) -> None:
        caption = self.gen_caption(map_id, name)
        if cache := await self.get_photo_cache(map_id, name):
            media = InputMediaPhoto(media=cache, caption=caption)
            await message.edit_media(media)
            return
        if cache := await self.get_doc_cache(map_id, name):
            media = InputMediaDocument(media=cache, caption=caption)
            await message.edit_media(media)
            return
        data = await self.map_helper.get_map(map_id, name)
        if len(data) > (1024 * 1024):
            data = BytesIO(data)
            data.name = "map.jpg"
            media = InputMediaDocument(media=data, caption=caption)
            msg = await message.edit_media(media)
            await self.set_doc_cache(map_id, name, msg.document.file_id)
        else:
            media = InputMediaPhoto(media=data, caption=caption)
            msg = await message.edit_media(media)
            await self.set_photo_cache(map_id, name, msg.photo[0].file_id)

    def get_show_map(self, name: str) -> List[int]:
        return [
            idx
            for idx, map_id in enumerate(self.map_helper.MAP_ID_LIST)
            if self.map_helper.get_label_count(map_id, name) > 0
        ]

    async def gen_map_button(
        self, maps: List[int], user_id: Union[str, int], name: str
    ) -> List[List[InlineKeyboardButton]]:
        return [
            [
                InlineKeyboardButton(
                    self.map_helper.MAP_NAME_LIST[idx],
                    callback_data=f"get_map|{user_id}|{self.map_helper.MAP_ID_LIST[idx]}|{name}",
                )
                for idx in maps
            ]
        ]

    async def send_media(self, message: Message, map_id: Union[str, int], name: str) -> None:
        caption = self.gen_caption(map_id, name)
        if cache := await self.get_photo_cache(map_id, name):
            await message.reply_photo(photo=cache, caption=caption)
            return
        if cache := await self.get_doc_cache(map_id, name):
            await message.reply_document(document=cache, caption=caption)
            return
        try:
            data = await self.map_helper.get_map(map_id, name)
        except MapException as e:
            await message.reply_text(e.message)
            return
        if len(data) > (1024 * 1024):
            data = BytesIO(data)
            data.name = "map.jpg"
            msg = await message.reply_document(document=data, caption=caption)
            await self.set_doc_cache(map_id, name, msg.document.file_id)
        else:
            msg = await message.reply_photo(photo=data, caption=caption)
            await self.set_photo_cache(map_id, name, msg.photo[0].file_id)

    def gen_caption(self, map_id: Union[int, str], name: str) -> str:
        count = self.map_helper.get_label_count(map_id, name)
        return f"派蒙一共找到了 {name} 的 {count} 个位置点\n* 数据来源于米游社wiki"

    @handler(CommandHandler, command="map", block=False)
    @handler(MessageHandler, filters=filters.Regex("^资源点查询(.*)"), block=False)
    @error_callable
    @restricts(restricts_time=20)
    async def command_start(self, update: Update, context: CallbackContext):
        message = update.effective_message
        args = context.args
        user = update.effective_user
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
        maps = self.get_show_map(resource_name)
        if len(maps) == 0:
            await message.reply_text("没有找到该资源。", parse_mode="Markdown")
            return
        if len(maps) == 1:
            map_id = self.map_helper.MAP_ID_LIST[maps[0]]
            await self.send_media(message, map_id, resource_name)
            return
        buttons = await self.gen_map_button(maps, user.id, resource_name)
        if isinstance(self.temp_photo, str):
            photo = self.temp_photo
        else:
            photo = open(self.temp_photo_path, "rb")
        reply_message = await message.reply_photo(
            photo=photo, caption="请选择你要查询的地图", reply_markup=InlineKeyboardMarkup(buttons)
        )
        if reply_message.photo:
            self.temp_photo = reply_message.photo[-1].file_id

    @handler(CallbackQueryHandler, pattern=r"^get_map\|", block=False)
    @restricts(restricts_time=3, without_overlapping=True)
    @error_callable
    async def get_player_cards(self, update: Update, _: CallbackContext) -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_map_callback(callback_query_data: str) -> Tuple[int, str, str]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _map_id = _data[2]
            _name = _data[3]
            logger.debug(f"callback_query_data 函数返回 user_id[{_user_id}] map_id[{_map_id}] name[{_name}]")
            return _user_id, _map_id, _name

        user_id, map_id, name = await get_map_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
        try:
            await self.edit_media(message, map_id, name)
        except MapException as e:
            await message.reply_text(e.message)

    @handler.command("refresh_map")
    @bot_admins_rights_check
    async def refresh_map(self, update: Update, _: CallbackContext):
        message = update.effective_message
        msg = await message.reply_text("正在刷新地图数据，请耐心等待...")
        await self.map_helper.refresh_query_map()
        await self.map_helper.refresh_label_count()
        await self.clear_cache()
        await msg.edit_text("正在刷新地图数据，请耐心等待...\n刷新成功")
