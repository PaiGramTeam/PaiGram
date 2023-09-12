from io import BytesIO
from typing import Optional
from urllib.parse import urlencode

from aiofiles import open as async_open
from simnet import GenshinClient, Region
from simnet.models.genshin.wish import BannerType
from telegram import Document, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, User
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import create_deep_linked_url

from core.basemodel import RegionEnum
from core.dependence.assets import AssetsService
from core.plugin import Plugin, conversation, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from metadata.scripts.paimon_moe import GACHA_LOG_PAIMON_MOE_PATH, update_paimon_moe_zh
from modules.gacha_log.error import (
    GachaLogAccountNotFound,
    GachaLogAuthkeyTimeout,
    GachaLogFileError,
    GachaLogInvalidAuthkey,
    GachaLogMixedProvider,
    GachaLogNotFound,
    PaimonMoeGachaLogFileError,
)
from modules.gacha_log.helpers import from_url_get_authkey
from modules.gacha_log.log import GachaLog
from plugins.tools.genshin import PlayerNotFoundError
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

INPUT_URL, INPUT_FILE, CONFIRM_DELETE = range(10100, 10103)


class WishLogPlugin(Plugin.Conversation):
    """抽卡记录导入/导出/分析"""

    def __init__(
        self,
        template_service: TemplateService,
        players_service: PlayersService,
        assets: AssetsService,
        cookie_service: CookiesService,
        player_info: PlayerInfoSystem,
    ):
        self.template_service = template_service
        self.players_service = players_service
        self.assets_service = assets
        self.cookie_service = cookie_service
        self.zh_dict = None
        self.gacha_log = GachaLog()
        self.player_info = player_info

    async def initialize(self) -> None:
        await update_paimon_moe_zh(False)
        async with async_open(GACHA_LOG_PAIMON_MOE_PATH, "r", encoding="utf-8") as load_f:
            self.zh_dict = jsonlib.loads(await load_f.read())

    async def get_player_id(self, uid: int) -> int:
        """获取绑定的游戏ID"""
        logger.debug("尝试获取已绑定的原神账号")
        player = await self.players_service.get_player(uid)
        if player is None:
            raise PlayerNotFoundError(uid)
        return player.player_id

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
            player_id = await self.get_player_id(user.id)
            if authkey:
                new_num = await self.gacha_log.get_gacha_log_data(user.id, player_id, authkey)
                return "更新完成，本次没有新增数据" if new_num == 0 else f"更新完成，本次共新增{new_num}条抽卡记录"
            if data:
                new_num = await self.gacha_log.import_gacha_log_data(user.id, player_id, data, verify_uid)
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
        except PlayerNotFoundError:
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

    async def gen_authkey(self, uid: int) -> Optional[str]:
        player_info = await self.players_service.get_player(uid, region=RegionEnum.HYPERION)
        if player_info is not None:
            cookies = await self.cookie_service.get(uid, account_id=player_info.account_id)
            if cookies is not None and cookies.data and "stoken" in cookies.data:
                if stuid := next((value for key, value in cookies.data.items() if key in ["ltuid", "login_uid"]), None):
                    cookies.data["stuid"] = stuid
                    async with GenshinClient(
                        cookies=cookies.data, region=Region.CHINESE, lang="zh-cn", player_id=player_info.player_id
                    ) as client:
                        return await client.get_authkey_by_stoken("webview_gacha")

    @conversation.entry_point
    @handler.command(command="gacha_log_import", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^导入抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        args = self.get_args(context)
        logger.info("用户 %s[%s] 导入抽卡记录命令请求", user.full_name, user.id)
        authkey = from_url_get_authkey(args[0] if args else "")
        if not args:
            authkey = await self.gen_authkey(user.id)
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
    async def import_data_from_message(self, update: Update, _: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        if message.document:
            await self.import_from_file(user, message)
            return ConversationHandler.END
        if not message.text:
            await message.reply_text("请发送文件或链接")
            return INPUT_URL
        authkey = from_url_get_authkey(message.text)
        reply = await message.reply_text("小派蒙正在从服务器获取数据，请稍后")
        await message.reply_chat_action(ChatAction.TYPING)
        text = await self._refresh_user_data(user, authkey=authkey)
        await reply.edit_text(text)
        return ConversationHandler.END

    @conversation.entry_point
    @handler.command(command="gacha_log_delete", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^删除抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    async def command_start_delete(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 删除抽卡记录命令请求", user.full_name, user.id)
        try:
            player_id = await self.get_player_id(user.id)
            context.chat_data["uid"] = player_id
        except PlayerNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号")
            return ConversationHandler.END
        _, status = await self.gacha_log.load_history_info(str(user.id), str(player_id), only_status=True)
        if not status:
            await message.reply_text("你还没有导入抽卡记录哦~")
            return ConversationHandler.END
        await message.reply_text("你确定要删除抽卡记录吗？（此项操作无法恢复），如果确定请发送 ”确定“，发送其他内容取消")
        return CONFIRM_DELETE

    @conversation.state(state=CONFIRM_DELETE)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def command_confirm_delete(self, update: Update, context: CallbackContext) -> int:
        message = update.effective_message
        user = update.effective_user
        if message.text == "确定":
            status = await self.gacha_log.remove_history_info(str(user.id), str(context.chat_data["uid"]))
            await message.reply_text("抽卡记录已删除" if status else "抽卡记录删除失败")
            return ConversationHandler.END
        await message.reply_text("已取消")
        return ConversationHandler.END

    @handler.command(command="gacha_log_force_delete", block=False, admin=True)
    async def command_gacha_log_force_delete(self, update: Update, context: CallbackContext):
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 强制删除抽卡记录命令请求", user.full_name, user.id)
        args = self.get_args(context)
        if not args:
            await message.reply_text("请指定用户ID")
            return
        try:
            cid = int(args[0])
            if cid < 0:
                raise ValueError("Invalid cid")
            player_id = await self.get_player_id(cid)
            _, status = await self.gacha_log.load_history_info(str(cid), str(player_id), only_status=True)
            if not status:
                await message.reply_text("该用户还没有导入抽卡记录")
                return
            status = await self.gacha_log.remove_history_info(str(cid), str(player_id))
            await message.reply_text("抽卡记录已强制删除" if status else "抽卡记录删除失败")
        except GachaLogNotFound:
            await message.reply_text("该用户还没有导入抽卡记录")
        except PlayerNotFoundError:
            await message.reply_text("该用户暂未绑定账号")
        except (ValueError, IndexError):
            await message.reply_text("用户ID 不合法")

    @handler.command(command="gacha_log_export", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^导出抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    async def command_start_export(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 导出抽卡记录命令请求", user.full_name, user.id)
        try:
            player_id = await self.get_player_id(user.id)
            await message.reply_chat_action(ChatAction.TYPING)
            path = await self.gacha_log.gacha_log_to_uigf(str(user.id), str(player_id))
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(document=open(path, "rb+"), caption="抽卡记录导出文件 - UIGF V2.3")
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
        except PlayerNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号")

    @handler.command(command="gacha_log_url", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^抽卡记录链接(.*)") & filters.ChatType.PRIVATE, block=False)
    async def command_start_url(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 生成抽卡记录链接命令请求", user.full_name, user.id)
        authkey = await self.gen_authkey(user.id)
        if not authkey:
            await message.reply_text("生成失败，仅国服且绑定 stoken 的用户才能生成抽卡记录链接")
        else:
            url = "https://hk4e-api.mihoyo.com/event/gacha_info/api/getGachaLog"
            params = {
                "authkey_ver": 1,
                "lang": "zh-cn",
                "gacha_type": 301,
                "authkey": authkey,
            }
            await message.reply_text(f"{url}?{urlencode(params)}", disable_web_page_preview=True)

    @handler.command(command="gacha_log", block=False)
    @handler.message(filters=filters.Regex("^抽卡记录?(武器|角色|常驻|)$"), block=False)
    async def command_start_analysis(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        pool_type = BannerType.CHARACTER1
        if args := self.get_args(context):
            if "武器" in args:
                pool_type = BannerType.WEAPON
            elif "常驻" in args:
                pool_type = BannerType.STANDARD
        logger.info("用户 %s[%s] 抽卡记录命令请求 || 参数 %s", user.full_name, user.id, pool_type.name)
        try:
            player_id = await self.get_player_id(user.id)
            await message.reply_chat_action(ChatAction.TYPING)
            data = await self.gacha_log.get_analysis(user.id, player_id, pool_type, self.assets_service)
            if isinstance(data, str):
                reply_message = await message.reply_text(data)
                if filters.ChatType.GROUPS.filter(message):
                    self.add_delete_message_job(reply_message, delay=300)
                    self.add_delete_message_job(message, delay=300)
            else:
                name_card = await self.player_info.get_name_card(player_id, user)
                await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
                data["name_card"] = name_card
                png_data = await self.template_service.render(
                    "genshin/wish_log/wish_log.jinja2",
                    data,
                    full_page=True,
                    file_type=FileType.DOCUMENT if len(data.get("fiveLog")) > 300 else FileType.PHOTO,
                    query_selector=".body_box",
                )
                if png_data.file_type == FileType.DOCUMENT:
                    await png_data.reply_document(message, filename="抽卡记录.png")
                else:
                    await png_data.reply_photo(message)
        except GachaLogNotFound:
            logger.info("未找到用户 %s[%s] 的抽卡记录", user.full_name, user.id)
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "gacha_log_import"))]
            ]
            await message.reply_text("派蒙没有找到你的抽卡记录，快来点击按钮私聊派蒙导入吧~", reply_markup=InlineKeyboardMarkup(buttons))

    @handler.command(command="gacha_count", block=False)
    @handler.message(filters=filters.Regex("^抽卡统计?(武器|角色|常驻|仅五星|)$"), block=False)
    async def command_start_count(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        pool_type = BannerType.CHARACTER1
        all_five = False
        if args := self.get_args(context):
            if "武器" in args:
                pool_type = BannerType.WEAPON
            elif "常驻" in args:
                pool_type = BannerType.STANDARD
            elif "仅五星" in args:
                all_five = True
        logger.info("用户 %s[%s] 抽卡统计命令请求 || 参数 %s || 仅五星 %s", user.full_name, user.id, pool_type.name, all_five)
        try:
            player_id = await self.get_player_id(user.id)
            group = filters.ChatType.GROUPS.filter(message)
            await message.reply_chat_action(ChatAction.TYPING)
            if all_five:
                data = await self.gacha_log.get_all_five_analysis(user.id, player_id, self.assets_service)
            else:
                data = await self.gacha_log.get_pool_analysis(user.id, player_id, pool_type, self.assets_service, group)
            if isinstance(data, str):
                reply_message = await message.reply_text(data)
                if filters.ChatType.GROUPS.filter(message):
                    self.add_delete_message_job(reply_message)
                    self.add_delete_message_job(message)
            else:
                name_card = await self.player_info.get_name_card(player_id, user)
                document = False
                if data["hasMore"] and not group:
                    document = True
                    data["hasMore"] = False
                data["name_card"] = name_card
                await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT if document else ChatAction.UPLOAD_PHOTO)
                png_data = await self.template_service.render(
                    "genshin/wish_count/wish_count.jinja2",
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
