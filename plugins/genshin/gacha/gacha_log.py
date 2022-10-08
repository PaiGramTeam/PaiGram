import json

from io import BytesIO
from genshin.models import BannerType

from telegram import Update, User, Message, Document
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters, ConversationHandler

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler, conversation
from core.template import TemplateService
from core.user import UserService
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

    def __init__(self, template_service: TemplateService = None, user_service: UserService = None,
                 assets: AssetsService = None):
        self.template_service = template_service
        self.user_service = user_service
        self.assets_service = assets

    @staticmethod
    def from_url_get_authkey(url: str) -> str:
        """从 UEL 解析 authkey
        :param url: URL
        :return: authkey
        """
        try:
            return url.split("authkey=")[1].split("&")[0]
        except IndexError:
            return url

    @staticmethod
    async def _refresh_user_data(user: User, data: dict = None, authkey: str = None) -> str:
        """刷新用户数据
        :param user: 用户
        :param data: 数据
        :param authkey: 认证密钥
        :return: 返回信息
        """
        try:
            logger.debug("尝试获取已绑定的原神账号")
            client = await get_genshin_client(user.id, need_cookie=False)
            if authkey:
                return await GachaLogService.get_gacha_log_data(user.id, client, authkey)
            if data:
                return await GachaLogService.import_gacha_log_data(user.id, data)
        except UserNotFoundError:
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            return "派蒙没有找到您所绑定的账号信息，请先私聊派蒙绑定账号"

    async def import_from_file(self, user: User, message: Message, document: Document = None) -> None:
        if not document:
            document = message.document
        if not document.file_name.endswith(".json"):
            await message.reply_text("文件格式错误，请发送符合 UIGF 标准的抽卡记录文件")
        if document.file_size > 50 * 1024 * 1024:
            await message.reply_text("文件过大，请发送小于 50MB 的文件")
        try:
            data = BytesIO()
            await (await document.get_file()).download(out=data)
            # bytesio to json
            data = data.getvalue().decode("utf-8")
            data = json.loads(data)
        except Exception as exc:
            logger.error(f"文件解析失败：{repr(exc)}")
            await message.reply_text("文件解析失败，请检查文件是否符合 UIGF 标准")
            return
        await message.reply_chat_action(ChatAction.TYPING)
        reply = await message.reply_text("文件解析成功，正在导入数据")
        try:
            text = await self._refresh_user_data(user, data=data)
        except Exception as exc:
            logger.error(f"文件解析失败：{repr(exc)}")
            text = "文件解析失败，请检查文件是否符合 UIGF 标准"
        await reply.edit_text(text)

    @conversation.entry_point
    @handler(CommandHandler, command="gacha_log_import", filters=filters.ChatType.PRIVATE, block=False)
    @handler(MessageHandler, filters=filters.Regex("^导入抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        args = get_all_args(context)
        logger.info(f"用户 {user.full_name}[{user.id}] 导入抽卡记录命令请求")
        if not args:
            if message.document:
                await self.import_from_file(user, message)
                return ConversationHandler.END
            elif message.reply_to_message and message.reply_to_message.document:
                await self.import_from_file(user, message, document=message.reply_to_message.document)
                return ConversationHandler.END
            await message.reply_text("<b>导入祈愿历史记录</b>\n\n"
                                     "请直接向派蒙发送从游戏中获取到的抽卡记录链接\n\n"
                                     "获取抽卡记录链接可以参考：https://paimon.moe/wish/import",
                                     parse_mode="html")
            return INPUT_URL
        authkey = self.from_url_get_authkey(args[0])
        data = await self._refresh_user_data(user, authkey=authkey)
        await message.reply_text(data)

    @conversation.state(state=INPUT_URL)
    @handler.message(filters=~filters.COMMAND, block=False)
    @restricts()
    @error_callable
    async def import_data_from_message(self, update: Update, _: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        if message.document:
            await self.import_from_file(user, message)
            return ConversationHandler.END
        authkey = self.from_url_get_authkey(message.text)
        reply = await message.reply_text("小派蒙正在从米哈游服务器获取数据，请稍后")
        text = await self._refresh_user_data(user, authkey=authkey)
        await reply.edit_text(text)
        return ConversationHandler.END

    @handler(CommandHandler, command="gacha_log_export", filters=filters.ChatType.PRIVATE, block=False)
    @handler(MessageHandler, filters=filters.Regex("^导出抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    @restricts()
    @error_callable
    async def command_start_export(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info(f"用户 {user.full_name}[{user.id}] 导出抽卡记录命令请求")
        try:
            client = await get_genshin_client(user.id, need_cookie=False)
            await message.reply_chat_action(ChatAction.TYPING)
            state, text, path = await GachaLogService.gacha_log_to_uigf(str(user.id), str(client.uid))
            if state:
                await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
                await message.reply_document(document=open(path, "rb+"), caption="抽卡记录导出文件")
            else:
                await message.reply_text(text)
        except UserNotFoundError:
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            await message.reply_text("未查询到您所绑定的账号信息，请先私聊派蒙绑定账号")

    @handler(CommandHandler, command="gacha_log", block=False)
    @handler(MessageHandler, filters=filters.Regex("^抽卡记录(.*)"), block=False)
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
            client = await get_genshin_client(user.id, need_cookie=False)
            await message.reply_chat_action(ChatAction.TYPING)
            data = await GachaLogService.get_analysis(user.id, client, pool_type, self.assets_service)
            if isinstance(data, str):
                reply_message = await message.reply_text(data)
                if filters.ChatType.GROUPS.filter(message):
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                    self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
            else:
                await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
                png_data = await self.template_service.render('genshin/gacha_log', "gacha_log.html", data,
                                                              full_page=True, query_selector=".body_box")
                await message.reply_photo(png_data)
        except UserNotFoundError:
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            await message.reply_text("未查询到您所绑定的账号信息，请先私聊派蒙绑定账号")

    @handler(CommandHandler, command="gacha_count", block=True)
    @handler(MessageHandler, filters=filters.Regex("^抽卡统计(.*)"), block=True)
    @restricts()
    @error_callable
    async def command_start_count(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        pool_type = BannerType.CHARACTER1
        if args := get_all_args(context):
            if "武器" in args:
                pool_type = BannerType.WEAPON
            elif "常驻" in args:
                pool_type = BannerType.STANDARD
        logger.info(f"用户 {user.full_name}[{user.id}] 抽卡统计命令请求 || 参数 {pool_type.name}")
        try:
            client = await get_genshin_client(user.id, need_cookie=False)
            group = filters.ChatType.GROUPS.filter(message)
            await message.reply_chat_action(ChatAction.TYPING)
            data = await GachaLogService.get_pool_analysis(user.id, client, pool_type, self.assets_service, group)
            if isinstance(data, str):
                reply_message = await message.reply_text(data)
                if filters.ChatType.GROUPS.filter(message):
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                    self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
            else:
                document = False
                if data["hasMore"] and not group:
                    document = True
                    data["hasMore"] = False
                png_data = await self.template_service.render('genshin/gacha_count', "gacha_count.html", data,
                                                              full_page=True, query_selector=".body_box")
                if document:
                    await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
                    await message.reply_document(png_data, filename="抽卡统计.png")
                else:
                    await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
                    await message.reply_photo(png_data)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            await message.reply_text("未查询到您所绑定的账号信息，请先私聊派蒙绑定账号")
