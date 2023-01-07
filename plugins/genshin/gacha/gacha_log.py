from io import BytesIO

import genshin
from aiofiles import open as async_open
from genshin.models import BannerType
from telegram import Update, User, Message, Document, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters, ConversationHandler
from telegram.helpers import create_deep_linked_url

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler, conversation
from core.template import TemplateService
from core.template.models import FileType
from core.user import UserService
from core.user.error import UserNotFoundError
from metadata.scripts.paimon_moe import update_paimon_moe_zh, GACHA_LOG_PAIMON_MOE_PATH
from modules.gacha_log.error import (
    GachaLogInvalidAuthkey,
    PaimonMoeGachaLogFileError,
    GachaLogFileError,
    GachaLogNotFound,
    GachaLogAccountNotFound,
    GachaLogMixedProvider,
    GachaLogAuthkeyTimeout,
)
from modules.gacha_log.helpers import from_url_get_authkey
from modules.gacha_log.log import GachaLog
from utils.bot import get_args
from utils.decorators.admins import bot_admins_rights_check
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.genshin import get_authkey_by_stoken
from utils.helpers import get_genshin_client
from utils.log import logger
from utils.models.base import RegionEnum

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

INPUT_URL, INPUT_FILE, CONFIRM_DELETE = range(10100, 10103)


class GachaLogPlugin(Plugin.Conversation, BasePlugin.Conversation):
    """抽卡记录导入/导出/分析"""

    def __init__(
        self,
        template_service: TemplateService = None,
        user_service: UserService = None,
        assets: AssetsService = None,
        cookie_service: CookiesService = None,
    ):
        self.template_service = template_service
        self.user_service = user_service
        self.assets_service = assets
        self.cookie_service = cookie_service
        self.zh_dict = None
        self.gacha_log = GachaLog()

    async def __async_init__(self):
        await update_paimon_moe_zh(False)
        async with async_open(GACHA_LOG_PAIMON_MOE_PATH, "r", encoding="utf-8") as load_f:
            self.zh_dict = jsonlib.loads(await load_f.read())

    async def _refresh_user_data(
        self, user: User, data: dict = None, authkey: str = None, verify_uid: bool = True
    ) -> str:
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
                new_num = await self.gacha_log.get_gacha_log_data(user.id, client, authkey)
                return "更新完成，本次没有新增数据" if new_num == 0 else f"更新完成，本次共新增{new_num}条抽卡记录"
            if data:
                new_num = await self.gacha_log.import_gacha_log_data(user.id, client, data, verify_uid)
                return "更新完成，本次没有新增数据" if new_num == 0 else f"更新完成，本次共新增{new_num}条抽卡记录"
        except GachaLogNotFound:
            return "派蒙没有找到你的抽卡记录，快来私聊派蒙导入吧~"
        except GachaLogAccountNotFound:
            return "导入失败，可能文件包含的祈愿记录所属 uid 与你当前绑定的 uid 不同"
        except GachaLogFileError:
            return "导入失败，数据格式错误"
        except GachaLogInvalidAuthkey:
            return "更新数据失败，authkey 无效"
        except GachaLogAuthkeyTimeout:
            return "更新数据失败，authkey 已经过期"
        except GachaLogMixedProvider:
            return "导入失败，你已经通过其他方式导入过抽卡记录了，本次无法导入"
        except UserNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            return "派蒙没有找到您所绑定的账号信息，请先私聊派蒙绑定账号"

    async def import_from_file(self, user: User, message: Message, document: Document = None) -> None:
        if not document:
            document = message.document
        # TODO: 使用 mimetype 判断文件类型
        if document.file_name.endswith(".xlsx"):
            file_type = "xlsx"
        elif document.file_name.endswith(".json"):
            file_type = "json"
        else:
            await message.reply_text("文件格式错误，请发送符合 UIGF 标准的抽卡记录文件或者 paimon.moe、非小酋导出的 xlsx 格式的抽卡记录文件")
            return
        if document.file_size > 2 * 1024 * 1024:
            await message.reply_text("文件过大，请发送小于 2 MB 的文件")
            return
        try:
            out = BytesIO()
            await (await document.get_file()).download_to_memory(out=out)
            if file_type == "json":
                # bytesio to json
                data = jsonlib.loads(out.getvalue().decode("utf-8"))
            elif file_type == "xlsx":
                data = self.gacha_log.convert_xlsx_to_uigf(out, self.zh_dict)
            else:
                await message.reply_text("文件解析失败，请检查文件")
                return
        except PaimonMoeGachaLogFileError as exc:
            await message.reply_text(
                f"导入失败，PaimonMoe的抽卡记录当前版本不支持\n支持抽卡记录的版本为 {exc.support_version}，你的抽卡记录版本为 {exc.file_version}"
            )
            return
        except GachaLogFileError:
            await message.reply_text("文件解析失败，请检查文件是否符合 UIGF 标准")
            return
        except (KeyError, IndexError, ValueError):
            await message.reply_text("文件解析失败，请检查文件编码是否正确或符合 UIGF 标准")
            return
        except Exception as exc:
            logger.error("文件解析失败 %s", repr(exc))
            await message.reply_text("文件解析失败，请检查文件是否符合 UIGF 标准")
            return
        await message.reply_chat_action(ChatAction.TYPING)
        reply = await message.reply_text("文件解析成功，正在导入数据")
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            text = await self._refresh_user_data(user, data=data, verify_uid=file_type == "json")
        except Exception as exc:  # pylint: disable=W0703
            logger.error("文件解析失败 %s", repr(exc))
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
        args = get_args(context)
        logger.info("用户 %s[%s] 导入抽卡记录命令请求", user.full_name, user.id)
        authkey = from_url_get_authkey(args[0] if args else "")
        if not args:
            if message.document:
                await self.import_from_file(user, message)
                return ConversationHandler.END
            elif message.reply_to_message and message.reply_to_message.document:
                await self.import_from_file(user, message, document=message.reply_to_message.document)
                return ConversationHandler.END
            try:
                user_info = await self.user_service.get_user_by_id(user.id)
            except UserNotFoundError:
                user_info = None
            if user_info and user_info.region == RegionEnum.HYPERION:
                try:
                    cookies = await self.cookie_service.get_cookies(user_info.user_id, user_info.region)
                except CookiesNotFoundError:
                    cookies = None
                if cookies and cookies.cookies and "stoken" in cookies.cookies:
                    if stuid := next(
                        (value for key, value in cookies.cookies.items() if key in ["ltuid", "login_uid"]), None
                    ):
                        cookies.cookies["stuid"] = stuid
                        client = genshin.Client(
                            cookies=cookies.cookies,
                            game=genshin.types.Game.GENSHIN,
                            region=genshin.Region.CHINESE,
                            lang="zh-cn",
                            uid=user_info.yuanshen_uid,
                        )
                        authkey = await get_authkey_by_stoken(client)
        if not authkey:
            await message.reply_text(
                "<b>开始导入祈愿历史记录：请通过 https://paimon.moe/wish/import 获取抽卡记录链接后发送给我"
                "（非 paimon.moe 导出的文件数据）</b>\n\n"
                "> 你还可以向派蒙发送从其他工具导出的 UIGF 标准的记录文件\n"
                "> 或者从 paimon.moe 、非小酋 导出的 xlsx 记录文件\n"
                "> 在绑定 Cookie 时添加 stoken 可能有特殊效果哦（仅限国服）\n"
                "<b>注意：导入的数据将会与旧数据进行合并。</b>",
                parse_mode="html",
            )
            return INPUT_URL
        text = "小派蒙正在从服务器获取数据，请稍后"
        if not args:
            text += "\n\n> 由于你绑定的 Cookie 中存在 stoken ，本次通过 stoken 自动刷新数据"
        reply = await message.reply_text(text)
        await message.reply_chat_action(ChatAction.TYPING)
        data = await self._refresh_user_data(user, authkey=authkey)
        await reply.edit_text(data)
        return ConversationHandler.END

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
        authkey = from_url_get_authkey(message.text)
        reply = await message.reply_text("小派蒙正在从服务器获取数据，请稍后")
        await message.reply_chat_action(ChatAction.TYPING)
        text = await self._refresh_user_data(user, authkey=authkey)
        await reply.edit_text(text)
        return ConversationHandler.END

    @conversation.entry_point
    @handler(CommandHandler, command="gacha_log_delete", filters=filters.ChatType.PRIVATE, block=False)
    @handler(MessageHandler, filters=filters.Regex("^删除抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    @restricts()
    @error_callable
    async def command_start_delete(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 删除抽卡记录命令请求", user.full_name, user.id)
        try:
            client = await get_genshin_client(user.id, need_cookie=False)
            context.chat_data["uid"] = client.uid
        except UserNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_uid"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
            return ConversationHandler.END
        _, status = await self.gacha_log.load_history_info(str(user.id), str(client.uid), only_status=True)
        if not status:
            await message.reply_text("你还没有导入抽卡记录哦~")
            return ConversationHandler.END
        await message.reply_text("你确定要删除抽卡记录吗？（此项操作无法恢复），如果确定请发送 ”确定“，发送其他内容取消")
        return CONFIRM_DELETE

    @conversation.state(state=CONFIRM_DELETE)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    @restricts()
    @error_callable
    async def command_confirm_delete(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        if message.text == "确定":
            status = await self.gacha_log.remove_history_info(str(user.id), str(context.chat_data["uid"]))
            await message.reply_text("抽卡记录已删除" if status else "抽卡记录删除失败")
            return ConversationHandler.END
        await message.reply_text("已取消")
        return ConversationHandler.END

    @handler(CommandHandler, command="gacha_log_force_delete", block=False)
    @bot_admins_rights_check
    async def command_gacha_log_force_delete(self, update: Update, context: CallbackContext):
        message = update.effective_message
        args = get_args(context)
        if not args:
            await message.reply_text("请指定用户ID")
            return
        try:
            cid = int(args[0])
            if cid < 0:
                raise ValueError("Invalid cid")
            client = await get_genshin_client(cid, need_cookie=False)
            _, status = await self.gacha_log.load_history_info(str(cid), str(client.uid), only_status=True)
            if not status:
                await message.reply_text("该用户还没有导入抽卡记录")
                return
            status = await self.gacha_log.remove_history_info(str(cid), str(client.uid))
            await message.reply_text("抽卡记录已强制删除" if status else "抽卡记录删除失败")
        except GachaLogNotFound:
            await message.reply_text("该用户还没有导入抽卡记录")
        except UserNotFoundError:
            await message.reply_text("该用户暂未绑定账号")
        except (ValueError, IndexError):
            await message.reply_text("用户ID 不合法")

    @handler(CommandHandler, command="gacha_log_export", filters=filters.ChatType.PRIVATE, block=False)
    @handler(MessageHandler, filters=filters.Regex("^导出抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    @restricts()
    @error_callable
    async def command_start_export(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 导出抽卡记录命令请求", user.full_name, user.id)
        try:
            client = await get_genshin_client(user.id, need_cookie=False)
            await message.reply_chat_action(ChatAction.TYPING)
            path = await self.gacha_log.gacha_log_to_uigf(str(user.id), str(client.uid))
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(document=open(path, "rb+"), caption="抽卡记录导出文件 - UIGF V2.2")
        except GachaLogNotFound:
            logger.info("未找到用户 %s[%s] 的抽卡记录", user.full_name, user.id)
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "gacha_log_import"))]
            ]
            await message.reply_text("派蒙没有找到你的抽卡记录，快来私聊派蒙导入吧~", reply_markup=InlineKeyboardMarkup(buttons))
        except GachaLogAccountNotFound:
            await message.reply_text("导入失败，可能文件包含的祈愿记录所属 uid 与你当前绑定的 uid 不同")
        except GachaLogFileError:
            await message.reply_text("导入失败，数据格式错误")
        except UserNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_uid"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))

    @handler(CommandHandler, command="gacha_log", block=False)
    @handler(MessageHandler, filters=filters.Regex("^抽卡记录?(武器|角色|常驻|)$"), block=False)
    @restricts()
    @error_callable
    async def command_start_analysis(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        pool_type = BannerType.CHARACTER1
        if args := get_args(context):
            if "武器" in args:
                pool_type = BannerType.WEAPON
            elif "常驻" in args:
                pool_type = BannerType.STANDARD
        logger.info("用户 %s[%s] 抽卡记录命令请求 || 参数 %s", user.full_name, user.id, pool_type.name)
        try:
            client = await get_genshin_client(user.id, need_cookie=False)
            await message.reply_chat_action(ChatAction.TYPING)
            data = await self.gacha_log.get_analysis(user.id, client, pool_type, self.assets_service)
            if isinstance(data, str):
                reply_message = await message.reply_text(data)
                if filters.ChatType.GROUPS.filter(message):
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                    self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
            else:
                await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
                png_data = await self.template_service.render(
                    "genshin/gacha_log/gacha_log.html", data, full_page=True, query_selector=".body_box"
                )
                await png_data.reply_photo(message)
        except GachaLogNotFound:
            logger.info("未找到用户 %s[%s] 的抽卡记录", user.full_name, user.id)
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "gacha_log_import"))]
            ]
            await message.reply_text("派蒙没有找到你的抽卡记录，快来点击按钮私聊派蒙导入吧~", reply_markup=InlineKeyboardMarkup(buttons))
        except UserNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_uid"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))

    @handler(CommandHandler, command="gacha_count", block=True)
    @handler(MessageHandler, filters=filters.Regex("^抽卡统计?(武器|角色|常驻|仅五星|)$"), block=True)
    @restricts()
    @error_callable
    async def command_start_count(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        pool_type = BannerType.CHARACTER1
        all_five = False
        if args := get_args(context):
            if "武器" in args:
                pool_type = BannerType.WEAPON
            elif "常驻" in args:
                pool_type = BannerType.STANDARD
            elif "仅五星" in args:
                all_five = True
        logger.info("用户 %s[%s] 抽卡统计命令请求 || 参数 %s || 仅五星 %s", user.full_name, user.id, pool_type.name, all_five)
        try:
            client = await get_genshin_client(user.id, need_cookie=False)
            group = filters.ChatType.GROUPS.filter(message)
            await message.reply_chat_action(ChatAction.TYPING)
            if all_five:
                data = await self.gacha_log.get_all_five_analysis(user.id, client, self.assets_service)
            else:
                data = await self.gacha_log.get_pool_analysis(user.id, client, pool_type, self.assets_service, group)
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
                await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT if document else ChatAction.UPLOAD_PHOTO)
                png_data = await self.template_service.render(
                    "genshin/gacha_count/gacha_count.html",
                    data,
                    full_page=True,
                    query_selector=".body_box",
                    file_type=FileType.DOCUMENT if document else FileType.PHOTO,
                )
                if document:
                    await png_data.reply_document(message, filename="抽卡统计.png")
                else:
                    await png_data.reply_photo(message)
        except GachaLogNotFound:
            logger.info("未找到用户 %s[%s] 的抽卡记录", user.full_name, user.id)
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "gacha_log_import"))]
            ]
            await message.reply_text("派蒙没有找到你的抽卡记录，快来私聊派蒙导入吧~", reply_markup=InlineKeyboardMarkup(buttons))
        except UserNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_uid"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
