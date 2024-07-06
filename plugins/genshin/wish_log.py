from functools import partial
from io import BytesIO
from typing import Optional, TYPE_CHECKING, List, Union, Tuple
from urllib.parse import urlencode

from aiofiles import open as async_open
from simnet import GenshinClient, Region
from simnet.models.genshin.wish import BannerType
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ConversationHandler, filters
from telegram.helpers import create_deep_linked_url

from core.basemodel import RegionEnum
from core.dependence.assets import AssetsService
from core.plugin import Plugin, conversation, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from gram_core.config import config
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from metadata.scripts.paimon_moe import GACHA_LOG_PAIMON_MOE_PATH, update_paimon_moe_zh
from modules.gacha_log.const import UIGF_VERSION, GACHA_TYPE_LIST_REVERSE
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
from modules.gacha_log.migrate import GachaLogMigrate
from modules.gacha_log.models import GachaLogInfo
from plugins.tools.genshin import PlayerNotFoundError
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


if TYPE_CHECKING:
    from telegram import Update, Message, User, Document
    from telegram.ext import ContextTypes
    from gram_core.services.players.models import Player
    from gram_core.services.template.models import RenderResult

INPUT_URL, INPUT_FILE, CONFIRM_DELETE = range(10100, 10103)
WAITING = f"小{config.notice.bot_name}正在从服务器获取数据，请稍后"
WISHLOG_NOT_FOUND = f"{config.notice.bot_name}没有找到你的抽卡记录，快来私聊{config.notice.bot_name}导入吧~"


class WishLogPlugin(Plugin.Conversation):
    """抽卡记录导入/导出/分析"""

    IMPORT_HINT = (
        "<b>开始导入祈愿历史记录：请通过 https://paimon.moe/wish/import 获取抽卡记录链接后发送给我"
        "（非 paimon.moe 导出的文件数据）</b>\n\n"
        f"> 你还可以向{config.notice.bot_name}发送从其他工具导出的 UIGF {UIGF_VERSION} 标准的记录文件\n"
        "> 或者从 paimon.moe 、非小酋 导出的 xlsx 记录文件\n"
        "> 在绑定 Cookie 时添加 stoken 可能有特殊效果哦（仅限国服）\n"
        "<b>注意：导入的数据将会与旧数据进行合并。</b>"
    )

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
        self.wish_photo = None

    async def initialize(self) -> None:
        await update_paimon_moe_zh(False)
        async with async_open(GACHA_LOG_PAIMON_MOE_PATH, "r", encoding="utf-8") as load_f:
            self.zh_dict = jsonlib.loads(await load_f.read())

    async def get_player_id(self, user_id: int, player_id: int, offset: int) -> int:
        """获取绑定的游戏ID"""
        logger.debug("尝试获取已绑定的原神账号")
        player = await self.players_service.get_player(user_id, player_id=player_id, offset=offset)
        if player is None:
            raise PlayerNotFoundError(user_id)
        return player.player_id

    async def _refresh_user_data(
        self, user: "User", player_id: int, data: dict = None, authkey: str = None, verify_uid: bool = True
    ) -> str:
        """刷新用户数据
        :param user: 用户
        :param data: 数据
        :param authkey: 认证密钥
        :return: 返回信息
        """
        try:
            logger.debug("尝试获取已绑定的原神账号")
            if authkey:
                new_num = await self.gacha_log.get_gacha_log_data(user.id, player_id, authkey)
                return "更新完成，本次没有新增数据" if new_num == 0 else f"更新完成，本次共新增{new_num}条抽卡记录"
            if data:
                new_num = await self.gacha_log.import_gacha_log_data(user.id, player_id, data, verify_uid)
                return "更新完成，本次没有新增数据" if new_num == 0 else f"更新完成，本次共新增{new_num}条抽卡记录"
        except GachaLogNotFound:
            return WAITING
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
            return config.notice.user_not_found

    async def import_from_file(
        self, user: "User", player_id: int, message: "Message", document: "Optional[Document]" = None
    ) -> None:
        if not document:
            document = message.document
        # TODO: 使用 mimetype 判断文件类型
        if document.file_name.endswith(".xlsx"):
            file_type = "xlsx"
        elif document.file_name.endswith(".json"):
            file_type = "json"
        else:
            await message.reply_text(
                "文件格式错误，请发送符合 UIGF 标准的抽卡记录文件或者 paimon.moe、非小酋导出的 xlsx 格式的抽卡记录文件"
            )
            return
        if document.file_size > 5 * 1024 * 1024:
            await message.reply_text("文件过大，请发送小于 5 MB 的文件")
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
            await message.reply_text(f"文件解析失败，请检查文件是否符合 UIGF {UIGF_VERSION} 标准")
            return
        except (KeyError, IndexError, ValueError):
            await message.reply_text(f"文件解析失败，请检查文件编码是否正确或符合 UIGF {UIGF_VERSION} 标准")
            return
        except Exception as exc:
            logger.error("文件解析失败 %s", repr(exc))
            await message.reply_text(f"文件解析失败，请检查文件是否符合 UIGF {UIGF_VERSION} 标准")
            return
        await message.reply_chat_action(ChatAction.TYPING)
        reply = await message.reply_text("文件解析成功，正在导入数据")
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            text = await self._refresh_user_data(user, player_id, data=data, verify_uid=file_type == "json")
        except Exception as exc:  # pylint: disable=W0703
            logger.error("文件解析失败 %s", repr(exc))
            text = f"文件解析失败，请检查文件是否符合 UIGF {UIGF_VERSION} 标准"
        await reply.edit_text(text)

    async def can_gen_authkey(self, user_id: int, player_id: int) -> bool:
        player_info = await self.players_service.get_player(user_id, region=RegionEnum.HYPERION, player_id=player_id)
        if player_info is not None:
            cookies = await self.cookie_service.get(user_id, account_id=player_info.account_id)
            if (
                cookies is not None
                and cookies.data
                and "stoken" in cookies.data
                and next((value for key, value in cookies.data.items() if key in ["ltuid", "login_uid"]), None)
            ):
                return True
        return False

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
    @handler.command(command="wish_log_import", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="gacha_log_import", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^导入抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    @handler.command(command="start", filters=filters.Regex("gacha_log_import$"), block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        user = update.effective_user
        player_id = await self.get_player_id(user.id, uid, offset)
        context.chat_data["uid"] = player_id
        logger.info("用户 %s[%s] 导入抽卡记录命令请求", user.full_name, user.id)
        keyboard = None
        if await self.can_gen_authkey(user.id, player_id):
            keyboard = ReplyKeyboardMarkup([["自动导入"], ["退出"]], one_time_keyboard=True)
        await message.reply_text(self.IMPORT_HINT, parse_mode="html", reply_markup=keyboard)
        return INPUT_URL

    @conversation.state(state=INPUT_URL)
    @handler.message(filters=~filters.COMMAND, block=False)
    async def import_data_from_message(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        user = update.effective_user
        player_id = context.chat_data["uid"]
        if message.document:
            await self.import_from_file(user, player_id, message)
            return ConversationHandler.END
        if not message.text:
            await message.reply_text("请发送文件或链接")
            return INPUT_URL
        if message.text == "自动导入":
            authkey = await self.gen_authkey(user.id)
            if not authkey:
                await message.reply_text(
                    "自动生成 authkey 失败，请尝试通过其他方式导入。", reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        elif message.text == "退出":
            await message.reply_text("取消导入抽卡记录", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            authkey = from_url_get_authkey(message.text)
        reply = await message.reply_text(WAITING, reply_markup=ReplyKeyboardRemove())
        await message.reply_chat_action(ChatAction.TYPING)
        text = await self._refresh_user_data(user, player_id, authkey=authkey)
        self.add_delete_message_job(reply, delay=1)
        await message.reply_text(text, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    @conversation.entry_point
    @handler.command(command="wish_log_delete", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="gacha_log_delete", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^删除抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    async def command_start_delete(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 删除抽卡记录命令请求", user.full_name, user.id)
        try:
            player_id = await self.get_player_id(user.id, uid, offset)
            context.chat_data["uid"] = player_id
        except PlayerNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            await message.reply_text(config.notice.user_not_found)
            return ConversationHandler.END
        _, status = await self.gacha_log.load_history_info(str(user.id), str(player_id), only_status=True)
        if not status:
            await message.reply_text("你还没有导入抽卡记录哦~")
            return ConversationHandler.END
        await message.reply_text(
            "你确定要删除抽卡记录吗？（此项操作无法恢复），如果确定请发送 ”确定“，发送其他内容取消"
        )
        return CONFIRM_DELETE

    @conversation.state(state=CONFIRM_DELETE)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def command_confirm_delete(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        user = update.effective_user
        if message.text == "确定":
            status = await self.gacha_log.remove_history_info(str(user.id), str(context.chat_data["uid"]))
            await message.reply_text("抽卡记录已删除" if status else "抽卡记录删除失败")
            return ConversationHandler.END
        await message.reply_text("已取消")
        return ConversationHandler.END

    @handler.command(command="wish_log_force_delete", block=False, admin=True)
    @handler.command(command="gacha_log_force_delete", block=False, admin=True)
    async def command_gacha_log_force_delete(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        uid, offset = self.get_real_uid_or_offset(update)
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
            player_id = await self.get_player_id(cid, uid, offset)
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

    @handler.command(command="wish_log_export", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="gacha_log_export", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^导出抽卡记录(.*)") & filters.ChatType.PRIVATE, block=False)
    async def command_start_export(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 导出抽卡记录命令请求", user.full_name, user.id)
        try:
            player_id = await self.get_player_id(user.id, uid, offset)
            await message.reply_chat_action(ChatAction.TYPING)
            path = await self.gacha_log.gacha_log_to_uigf(str(user.id), str(player_id))
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(document=open(path, "rb+"), caption=f"抽卡记录导出文件 - UIGF {UIGF_VERSION}")
        except GachaLogNotFound:
            logger.info("未找到用户 %s[%s] 的抽卡记录", user.full_name, user.id)
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "gacha_log_import"))]
            ]
            await message.reply_text(WISHLOG_NOT_FOUND, reply_markup=InlineKeyboardMarkup(buttons))
        except GachaLogAccountNotFound:
            await message.reply_text("导入失败，可能文件包含的祈愿记录所属 uid 与你当前绑定的 uid 不同")
        except GachaLogFileError:
            await message.reply_text("导入失败，数据格式错误")
        except PlayerNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            await message.reply_text(config.notice.user_not_found)

    @handler.command(command="wish_log_url", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="gacha_log_url", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^抽卡记录链接(.*)") & filters.ChatType.PRIVATE, block=False)
    async def command_start_url(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
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

    async def rander_wish_log_analysis(
        self, user_id: int, player_id: int, pool_type: BannerType
    ) -> Union[str, "RenderResult"]:
        data = await self.gacha_log.get_analysis(user_id, player_id, pool_type, self.assets_service)
        if isinstance(data, str):
            return data
        name_card = await self.player_info.get_name_card(player_id, user_id)
        data["name_card"] = name_card
        png_data = await self.template_service.render(
            "genshin/wish_log/wish_log.jinja2",
            data,
            full_page=True,
            file_type=FileType.DOCUMENT if len(data.get("fiveLog")) > 300 else FileType.PHOTO,
            query_selector=".body_box",
        )
        return png_data

    @staticmethod
    def gen_button(user_id: int, uid: int, info: "GachaLogInfo") -> List[List[InlineKeyboardButton]]:
        buttons = []
        pools = []
        skip_pools = []
        for k, v in info.item_list.items():
            if k in skip_pools:
                continue
            if not v:
                continue
            pools.append(k)
        # 2 个一组
        for i in range(0, len(pools), 2):
            row = []
            for pool in pools[i : i + 2]:
                for k, v in {"log": "", "count": "（按卡池）"}.items():
                    row.append(
                        InlineKeyboardButton(
                            f"{pool.replace('祈愿', '')}{v}",
                            callback_data=f"get_wish_log|{user_id}|{uid}|{k}|{pool}",
                        )
                    )
            buttons.append(row)
        buttons.append([InlineKeyboardButton("五星抽卡统计", callback_data=f"get_wish_log|{user_id}|{uid}|count|five")])
        return buttons

    async def wish_log_pool_choose(self, user_id: int, player_id: int, message: "Message"):
        await message.reply_chat_action(ChatAction.TYPING)
        gacha_log, status = await self.gacha_log.load_history_info(str(user_id), str(player_id))
        if not status:
            raise GachaLogNotFound
        buttons = self.gen_button(user_id, player_id, gacha_log)
        if isinstance(self.wish_photo, str):
            photo = self.wish_photo
        else:
            photo = open("resources/img/wish.jpg", "rb")
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        reply_message = await message.reply_photo(
            photo=photo,
            caption="请选择你要查询的卡池",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        if reply_message.photo:
            self.wish_photo = reply_message.photo[-1].file_id

    async def wish_log_pool_send(self, user_id: int, uid: int, pool_type: "BannerType", message: "Message"):
        await message.reply_chat_action(ChatAction.TYPING)
        png_data = await self.rander_wish_log_analysis(user_id, uid, pool_type)
        if isinstance(png_data, str):
            reply = await message.reply_text(png_data)
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply)
                self.add_delete_message_job(message)
        else:
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            if png_data.file_type == FileType.DOCUMENT:
                await png_data.reply_document(message, filename="抽卡统计.png")
            else:
                await png_data.reply_photo(message)

    @handler.command(command="wish_log", block=False)
    @handler.command(command="gacha_log", block=False)
    @handler.message(filters=filters.Regex("^抽卡记录?(武器|角色|常驻|)$"), block=False)
    async def command_start_analysis(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        pool_type = None
        if args := self.get_args(context):
            if "角色" in args:
                pool_type = BannerType.CHARACTER1
            elif "武器" in args:
                pool_type = BannerType.WEAPON
            elif "常驻" in args:
                pool_type = BannerType.STANDARD
            elif "集录" in args:
                pool_type = BannerType.CHRONICLED
        self.log_user(update, logger.info, "抽卡记录命令请求 || 参数 %s", pool_type.name if pool_type else None)
        try:
            player_id = await self.get_player_id(user_id, uid, offset)
            if pool_type is None:
                await self.wish_log_pool_choose(user_id, player_id, message)
            else:
                await self.wish_log_pool_send(user_id, player_id, pool_type, message)
        except GachaLogNotFound:
            self.log_user(update, logger.info, "未找到抽卡记录")
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "gacha_log_import"))]
            ]
            await message.reply_text(WISHLOG_NOT_FOUND, reply_markup=InlineKeyboardMarkup(buttons))

    @handler.callback_query(pattern=r"^get_wish_log\|", block=False)
    async def get_wish_log(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_wish_log_callback(
            callback_query_data: str,
        ) -> Tuple[str, str, int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            _t = _data[3]
            _result = _data[4]
            logger.debug(
                "callback_query_data函数返回 result[%s] user_id[%s] uid[%s] show_type[%s]",
                _result,
                _user_id,
                _uid,
                _t,
            )
            return _result, _t, _user_id, _uid

        try:
            pool, show_type, user_id, uid = await get_wish_log_callback(callback_query.data)
        except IndexError:
            await callback_query.answer("按钮数据已过期，请重新获取。", show_alert=True)
            self.add_delete_message_job(message, delay=1)
            return
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        if show_type == "count":
            await self.get_wish_log_count(update, user_id, uid, pool)
        else:
            await self.get_wish_log_log(update, user_id, uid, pool)

    async def get_wish_log_log(self, update: "Update", user_id: int, uid: int, pool: str):
        callback_query = update.callback_query
        message = callback_query.message

        pool_type = GACHA_TYPE_LIST_REVERSE.get(pool)
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            png_data = await self.rander_wish_log_analysis(user_id, uid, pool_type)
        except GachaLogNotFound:
            png_data = "未找到抽卡记录"
        if isinstance(png_data, str):
            await callback_query.answer(png_data, show_alert=True)
            self.add_delete_message_job(message, delay=1)
        else:
            await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            if png_data.file_type == FileType.DOCUMENT:
                await png_data.reply_document(message, filename="抽卡统计.png")
                self.add_delete_message_job(message, delay=1)
            else:
                await png_data.edit_media(message)

    async def get_wish_log_count(self, update: "Update", user_id: int, uid: int, pool: str):
        callback_query = update.callback_query
        message = callback_query.message

        all_five = pool == "five"
        group = filters.ChatType.GROUPS.filter(message)
        pool_type = GACHA_TYPE_LIST_REVERSE.get(pool)
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            if all_five:
                png_data = await self.gacha_log.get_all_five_analysis(user_id, uid, self.assets_service)
            else:
                png_data = await self.gacha_log.get_pool_analysis(user_id, uid, pool_type, self.assets_service, group)
        except GachaLogNotFound:
            png_data = "未找到抽卡记录"
        if isinstance(png_data, str):
            await callback_query.answer(png_data, show_alert=True)
            self.add_delete_message_job(message, delay=1)
        else:
            await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
            name_card = await self.player_info.get_name_card(uid, user_id)
            document = False
            if png_data["hasMore"] and not group:
                document = True
                png_data["hasMore"] = False
            png_data["name_card"] = name_card
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT if document else ChatAction.UPLOAD_PHOTO)
            png = await self.template_service.render(
                "genshin/wish_count/wish_count.jinja2",
                png_data,
                full_page=True,
                query_selector=".body_box",
                file_type=FileType.DOCUMENT if document else FileType.PHOTO,
            )
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            if document:
                await png.reply_document(message, filename="抽卡统计.png")
                self.add_delete_message_job(message, delay=1)
            else:
                await png.edit_media(message)

    @staticmethod
    async def get_migrate_data(
        old_user_id: int, new_user_id: int, old_players: List["Player"]
    ) -> Optional[GachaLogMigrate]:
        return await GachaLogMigrate.create(old_user_id, new_user_id, old_players)

    async def wish_log_use_by_inline(
        self, update: "Update", context: "ContextTypes.DEFAULT_TYPE", pool_type: "BannerType"
    ):
        callback_query = update.callback_query
        user = update.effective_user
        user_id = user.id
        uid = IInlineUseData.get_uid_from_context(context)

        self.log_user(update, logger.info, "抽卡记录命令请求 || 参数 %s", pool_type.name if pool_type else None)
        notice = None
        try:
            render_result = await self.rander_wish_log_analysis(user_id, uid, pool_type)
            if isinstance(render_result, str):
                notice = render_result
            else:
                await render_result.edit_inline_media(callback_query, filename="抽卡统计.png")
        except GachaLogNotFound:
            self.log_user(update, logger.info, "未找到抽卡记录")
            notice = "未找到抽卡记录"
        if notice:
            await callback_query.answer(notice, show_alert=True)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        types = {
            "角色": BannerType.CHARACTER1,
            "武器": BannerType.WEAPON,
            "常驻": BannerType.STANDARD,
            "集录": BannerType.CHRONICLED,
        }
        data = []
        for k, v in types.items():
            data.append(
                IInlineUseData(
                    text=f"{k}祈愿",
                    hash=f"wish_log_{v.value}",
                    callback=partial(self.wish_log_use_by_inline, pool_type=v),
                    player=True,
                )
            )
        return data
