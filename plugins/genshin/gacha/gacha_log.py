import json
import os
from io import BytesIO

import genshin
from pyppeteer import launch
from genshin.models import BannerType
from telegram import Update, User
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters, ConversationHandler

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler, conversation
from core.template import TemplateService
from core.user.error import UserNotFoundError
from modules.apihelper.gacha_log import GachaLog as GachaLogService
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger

INPUT_URL, INPUT_FILE = 10100, 10101


class GachaLog(Plugin.Conversation, BasePlugin.Conversation):
    """ 抽卡记录导入/导出/分析"""

    def __init__(self, template_service: TemplateService = None, assets: AssetsService = None):
        self.template_service = template_service
        self.browser: launch = None
        self.current_dir = os.getcwd()
        self.resources_dir = os.path.join(self.current_dir, "resources")
        self.character_gacha_card = {}
        self.user_time = {}
        self.assets_service = assets

    @staticmethod
    def from_url_get_authkey(url: str) -> str:
        try:
            return url.split("authkey=")[1].split("&")[0]
        except IndexError:
            return url

    @staticmethod
    async def _refresh_user_data(user: User, data: dict = None, authkey: str = None):
        try:
            logger.debug("尝试获取已绑定的原神账号")
            client = await get_genshin_client(user.id)
            if authkey:
                return await GachaLogService.get_gacha_log_data(user.id, client, authkey)
            if data:
                return await GachaLogService.import_gacha_log_data(user.id, data)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            return "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号"

    @conversation.entry_point
    @handler(CommandHandler, command="gacha_log_refresh", filters=filters.ChatType.PRIVATE, block=True)
    @handler(MessageHandler, filters=filters.Regex("^更新抽卡记录(.*)") & filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        args = get_all_args(context)
        if not args:
            await message.reply_text("请发送从游戏中获取到的抽卡记录链接\n\n"
                                     "获取抽卡记录链接教程：https://paimon.moe/wish/import")
            return INPUT_URL
        authkey = self.from_url_get_authkey(args[0])
        data = await self._refresh_user_data(user, authkey=authkey)
        await message.reply_text(data)

    @conversation.state(state=INPUT_URL)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND,
                     block=True)
    @restricts()
    @error_callable
    async def import_data_from_url(self, update: Update, _: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        authkey = self.from_url_get_authkey(message.text)
        reply = await message.reply_text("正在从米哈游服务器获取数据，请稍后")
        text = await self._refresh_user_data(user, authkey=authkey)
        await reply.edit_text(text)
        return ConversationHandler.END

    @handler(CommandHandler, command="gacha_log_import", filters=filters.ChatType.PRIVATE, block=True)
    @handler(MessageHandler, filters=filters.Regex("^导入抽卡记录(.*)") & filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start_import(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        if message.reply_to_message:
            document = message.reply_to_message.document
        else:
            document = message.document
        if not document:
            await message.reply_text("请回复符合 UIGF 标准的抽卡记录文件")
            return
        if not document.file_name.endswith(".json"):
            await message.reply_text("文件格式错误，请发送符合 UIGF 标准的抽卡记录文件")
            return
        if document.file_size > 50 * 1024 * 1024:
            await message.reply_text("文件过大，请发送小于 50MB 的文件")
            return
        try:
            data = BytesIO()
            await (await document.get_file()).download(out=data)
            # bytesio to json
            data = data.getvalue().decode("utf-8")
            data = json.loads(data)
        except Exception:
            await message.reply_text("文件解析失败，请检查文件是否符合 UIGF 标准")
            return
        reply = await message.reply_text("文件解析成功，正在导入数据")
        try:
            text = await self._refresh_user_data(user, data=data)
        except Exception:
            await reply.edit_text("文件解析失败，请检查文件是否符合 UIGF 标准")
            return
        await reply.edit_text(text)
        return

    @handler(CommandHandler, command="gacha_log_export", filters=filters.ChatType.PRIVATE, block=True)
    @handler(MessageHandler, filters=filters.Regex("^导出抽卡记录(.*)") & filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start_export(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        try:
            client = await get_genshin_client(user.id)
            state, text, path = await GachaLogService.gacha_log_to_uigf(str(user.id), str(client.uid))
            if state:
                await message.reply_document(document=open(path, "rb+"), caption="抽卡记录导出文件")
            else:
                await message.reply_text(text)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            await message.reply_text("未查询到您所绑定的账号信息，请先私聊派蒙绑定账号")
            return

    @handler(CommandHandler, command="gacha_log", filters=filters.ChatType.PRIVATE, block=True)
    @handler(MessageHandler, filters=filters.Regex("^抽卡记录(.*)") & filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start_analysis(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        pool_type = BannerType.CHARACTER1
        if args := get_all_args(context):
            if "武器" in args:
                pool_type = BannerType.WEAPON
            elif "常驻" in args:
                pool_type = BannerType.STANDARD
        logger.info(f"用户 {user.full_name}[{user.id}] 抽卡记录命令请求 || 参数 {pool_type.name}")
        try:
            client = await get_genshin_client(user.id)
            data = await GachaLogService.get_analysis(user.id, client, pool_type, self.assets_service)
            if isinstance(data, str):
                reply_message = await message.reply_text(data)
            else:
                await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
                png_data = await self.template_service.render('genshin/gachaLog', "gachaLog.html", data,
                                                              full_page=True, query_selector=".body_box")
                reply_message = await message.reply_photo(png_data)
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            await message.reply_text("未查询到您所绑定的账号信息，请先私聊派蒙绑定账号")
            return
