from functools import partial
from typing import Optional, TYPE_CHECKING, List, Union, Tuple
from simnet.models.genshin.wish import GenshinBeyondBannerType
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatAction
from telegram.ext import filters
from telegram.helpers import create_deep_linked_url

from core.dependence.assets.impl.genshin import AssetsService
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from gram_core.config import config
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from gram_core.services.gacha_log_rank.services import GachaLogRankService
from modules.beyond_gacha_log.const import GACHA_TYPE_LIST_REVERSE
from modules.gacha_log.error import GachaLogNotFound
from modules.beyond_gacha_log.log import BeyondGachaLog
from modules.beyond_gacha_log.migrate import BeyondGachaLogMigrate
from modules.beyond_gacha_log.models import BeyondGachaLogInfo
from plugins.tools.genshin import PlayerNotFoundError
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


if TYPE_CHECKING:
    from telegram import Update, Message
    from telegram.ext import ContextTypes
    from gram_core.services.players.models import Player
    from gram_core.services.template.models import RenderResult

WISHLOG_NOT_FOUND = f"{config.notice.bot_name}没有找到你的颂愿记录，快来私聊{config.notice.bot_name}导入吧~"


class BeyondWishLogPlugin(Plugin.Conversation):
    """颂愿记录导入/导出/分析"""

    def __init__(
        self,
        template_service: TemplateService,
        players_service: PlayersService,
        assets: AssetsService,
        cookie_service: CookiesService,
        player_info: PlayerInfoSystem,
        gacha_log_rank: GachaLogRankService,
    ):
        self.template_service = template_service
        self.players_service = players_service
        self.assets_service = assets
        self.cookie_service = cookie_service
        self.gacha_log = BeyondGachaLog(gacha_log_rank_service=gacha_log_rank)
        self.player_info = player_info
        self.wish_photo = None

    async def get_player_id(self, user_id: int, player_id: int, offset: int) -> int:
        """获取绑定的游戏ID"""
        logger.debug("尝试获取已绑定的原神账号")
        player = await self.players_service.get_player(user_id, player_id=player_id, offset=offset)
        if player is None:
            raise PlayerNotFoundError(user_id)
        return player.player_id

    async def rander_wish_log_analysis(
        self, user_id: int, player_id: int, pool_type: "GenshinBeyondBannerType"
    ) -> Union[str, "RenderResult"]:
        data = await self.gacha_log.get_analysis(user_id, player_id, pool_type, self.assets_service)
        if isinstance(data, str):
            return data
        name_card = await self.player_info.get_name_card(player_id, user_id)
        data["name_card"] = name_card
        data["pool_type"] = pool_type.value
        png_data = await self.template_service.render(
            "genshin/wish_log/wish_log.jinja2",
            data,
            full_page=True,
            file_type=FileType.DOCUMENT if len(data.get("fiveLog")) > 300 else FileType.PHOTO,
            query_selector=".body_box",
        )
        return png_data

    @staticmethod
    def gen_button(user_id: int, uid: int, info: "BeyondGachaLogInfo") -> List[List[InlineKeyboardButton]]:
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
                            f"{pool.replace('颂愿', '')}{v}",
                            callback_data=f"get_beyond_wish_log|{user_id}|{uid}|{k}|{pool}",
                        )
                    )
            buttons.append(row)
        buttons.append(
            [InlineKeyboardButton("套装抽卡统计", callback_data=f"get_beyond_wish_log|{user_id}|{uid}|count|five")]
        )
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
            photo = open("resources/img/beyond.png", "rb")
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        reply_message = await message.reply_photo(
            photo=photo,
            caption="请选择你要查询的颂愿卡池",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        if reply_message.photo:
            self.wish_photo = reply_message.photo[-1].file_id

    async def wish_log_pool_send(
        self, user_id: int, uid: int, pool_type: "GenshinBeyondBannerType", message: "Message"
    ):
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

    @handler.command(command="beyond_wish_log", block=False)
    @handler.command(command="beyond_gacha_log", block=False)
    async def command_start_analysis(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        pool_type = None
        if args := self.get_args(context):
            if "活动" in args:
                pool_type = GenshinBeyondBannerType.EVENT
            elif "常驻" in args:
                pool_type = GenshinBeyondBannerType.STANDARD
        self.log_user(update, logger.info, "颂愿颂愿记录命令请求 || 参数 %s", pool_type.name if pool_type else None)
        try:
            player_id = await self.get_player_id(user_id, uid, offset)
            if pool_type is None:
                await self.wish_log_pool_choose(user_id, player_id, message)
            else:
                await self.wish_log_pool_send(user_id, player_id, pool_type, message)
        except GachaLogNotFound:
            self.log_user(update, logger.info, "未找到颂愿记录")
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "gacha_log_import"))]
            ]
            await message.reply_text(WISHLOG_NOT_FOUND, reply_markup=InlineKeyboardMarkup(buttons))

    @handler.callback_query(pattern=r"^get_beyond_wish_log\|", block=False)
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
            png_data = "未找到颂愿记录"
        if isinstance(png_data, str):
            await callback_query.answer(png_data, show_alert=True)
            self.add_delete_message_job(message, delay=1)
        else:
            await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            if png_data.file_type == FileType.DOCUMENT:
                await png_data.reply_document(
                    message,
                    filename="抽卡统计.png",
                )
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
            png_data = "未找到颂愿记录"
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
                await png.reply_document(
                    message,
                    filename="抽卡统计.png",
                )
                self.add_delete_message_job(message, delay=1)
            else:
                await png.edit_media(message)

    @staticmethod
    async def get_migrate_data(
        old_user_id: int, new_user_id: int, old_players: List["Player"]
    ) -> Optional[BeyondGachaLogMigrate]:
        return await BeyondGachaLogMigrate.create(old_user_id, new_user_id, old_players)

    async def wish_log_use_by_inline(
        self, update: "Update", context: "ContextTypes.DEFAULT_TYPE", pool_type: "GenshinBeyondBannerType"
    ):
        callback_query = update.callback_query
        user = update.effective_user
        user_id = user.id
        uid = IInlineUseData.get_uid_from_context(context)

        self.log_user(update, logger.info, "颂愿记录命令请求 || 参数 %s", pool_type.name if pool_type else None)
        notice = None
        try:
            render_result = await self.rander_wish_log_analysis(user_id, uid, pool_type)
            if isinstance(render_result, str):
                notice = render_result
            else:
                await render_result.edit_inline_media(callback_query, filename="抽卡统计.png")
        except GachaLogNotFound:
            self.log_user(update, logger.info, "未找到颂愿记录")
            notice = "未找到颂愿记录"
        if notice:
            await callback_query.answer(notice, show_alert=True)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        types = {
            "活动": GenshinBeyondBannerType.EVENT,
            "常驻": GenshinBeyondBannerType.STANDARD,
        }
        data = []
        for k, v in types.items():
            data.append(
                IInlineUseData(
                    text=f"{k}颂愿",
                    hash=f"beyond_wish_log_{v.value}",
                    callback=partial(self.wish_log_use_by_inline, pool_type=v),
                    player=True,
                )
            )
        return data
