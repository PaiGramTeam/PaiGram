import asyncio
import math
from datetime import datetime
from functools import partial
from typing import Dict, Tuple, List, TYPE_CHECKING, Optional

from pydantic import BaseModel

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import filters

from core.dependence.assets import AssetsService, AssetsCouldNotFound
from gram_core.config import config
from gram_core.plugin import Plugin, handler
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from gram_core.services.template.services import TemplateService

from metadata.pool.pool import POOL_301 as CHARACTER_POOL, POOL_302 as WEAPON_POOL, POOL_500 as MIX_POOL
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

    from gram_core.services.template.models import RenderResult


class WishWaitingListData(BaseModel):
    name: str
    """名称"""
    icon: Optional[str] = None
    """图标"""
    up_times: int
    """总共 UP 次数"""
    last_up_time: datetime
    """上一次 UP 时间"""
    last_up_day: int
    """距离上一次 UP 多少天"""


class WishWaitingListPlugin(Plugin):
    """未复刻列表"""

    def __init__(
        self,
        assets: AssetsService,
        template_service: TemplateService,
        player_info: PlayerInfoSystem,
    ):
        self.assets_service = assets
        self.template_service = template_service
        self.player_info = player_info
        self.waiting_list = {}

    async def initialize(self) -> None:
        asyncio.create_task(self.init_data())

    async def init_data(self):
        now = datetime.now()
        if self.waiting_list and (now - self.waiting_list["time"]).total_seconds() < 3600:
            return
        data = {
            "avatar": await self._get_waiting_list(CHARACTER_POOL, "avatar", self.assets_service.avatar),
            "weapon": await self._get_waiting_list(WEAPON_POOL, "weapon", self.assets_service.weapon),
            "time": now,
        }
        self.waiting_list.update(data)

    @staticmethod
    async def _ignore_static_pool(pool_type: str):
        if pool_type == "avatar":
            return ["莫娜", "七七", "迪卢克", "琴", "提纳里", "刻晴", "迪希雅"]
        return []

    @staticmethod
    async def _ignore_mix_pool(
        pool_type: str,
        five_times: Dict[str, WishWaitingListData],
        four_times: Dict[str, WishWaitingListData],
    ):
        now = datetime.now()
        for p in MIX_POOL:
            does = p[pool_type]
            last_up_time = datetime.strptime(p["to"], "%Y-%m-%d %H:%M:%S")
            last_up_day = math.ceil((now - last_up_time).total_seconds() / 86400)
            for do in does:
                t: WishWaitingListData = five_times.get(do) or four_times.get(do)
                if not t:
                    continue
                t.up_times += 1
                if t.last_up_time < last_up_time:
                    t.last_up_time = last_up_time
                    t.last_up_day = last_up_day

    async def _get_waiting_list(
        self,
        pool,
        pool_type: str,
        assets,
    ) -> Tuple[Dict[str, WishWaitingListData], List[str], Dict[str, WishWaitingListData], List[str]]:
        now = datetime.now()
        five_times: Dict[str, WishWaitingListData] = {}
        five_data = []
        four_times: Dict[str, WishWaitingListData] = {}
        four_data = []
        ignore = await self._ignore_static_pool(pool_type)
        for p in pool:
            fives = p["five"]
            fours = p["four"]
            last_up_time = datetime.strptime(p["to"], "%Y-%m-%d %H:%M:%S")
            last_up_day = max(math.ceil((now - last_up_time).total_seconds() / 86400), 0)
            for i, times in [(fives, five_times), (fours, four_times)]:
                for n in i:
                    if n in ignore:
                        continue
                    if n in times:
                        times[n].up_times += 1
                    else:
                        try:
                            icon = (await assets(n).icon()).as_uri()
                        except AssetsCouldNotFound:
                            icon = ""
                        times[n] = WishWaitingListData(
                            name=n,
                            icon=icon,
                            up_times=1,
                            last_up_time=last_up_time,
                            last_up_day=last_up_day,
                        )
        await self._ignore_mix_pool(pool_type, five_times, four_times)
        for times, data in [(five_times, five_data), (four_times, four_data)]:
            data.clear()
            data.extend(list(times.keys()))
            data.sort(key=lambda j: times[j].last_up_day, reverse=True)  # pylint: disable=W0640
        return five_times, five_data, four_times, four_data

    @handler.command("wish_waiting_list", block=False)
    @handler.message(filters=filters.Regex(r"^未复刻列表?(角色|武器|)$"), block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        is_avatar = True
        if args := self.get_args(context):
            if "角色" in args:
                is_avatar = True
            elif "武器" in args:
                is_avatar = False
        self.log_user(update, logger.info, "查询未复刻列表 is_avatar[%s]", is_avatar)
        await message.reply_chat_action(ChatAction.TYPING)
        image = await self.render(user_id, is_avatar)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await image.reply_photo(message, reply_markup=await self.get_wish_waiting_list_button(user_id, is_avatar))

    async def render(self, user_id: int, is_avatar: bool) -> "RenderResult":
        await self.init_data()
        _data = self.waiting_list["avatar" if is_avatar else "weapon"]
        data = {
            "fiveLog": _data[1],
            "fiveData": _data[0],
            "fourLog": _data[3],
            "fourData": _data[2],
        }
        name_card = await self.player_info.get_name_card(None, user_id)
        data["name_card"] = name_card
        return await self.template_service.render(
            "genshin/wish_log/wish_waiting_list.jinja2",
            data,
            full_page=True,
            query_selector=".body_box",
        )

    @staticmethod
    async def get_wish_waiting_list_button(user_id: int, is_avatar: bool):
        return InlineKeyboardMarkup(
            [
                [
                    (
                        InlineKeyboardButton(
                            ">> 切换到武器池 <<", callback_data=f"get_wish_waiting_list|{user_id}|weapon"
                        )
                        if is_avatar
                        else InlineKeyboardButton(
                            ">> 切换到角色池 <<", callback_data=f"get_wish_waiting_list|{user_id}|avatar"
                        )
                    )
                ]
            ]
        )

    @handler.callback_query(pattern=r"^get_wish_waiting_list\|", block=False)
    async def get_wish_waiting_list(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_wish_waiting_list_callback(
            callback_query_data: str,
        ) -> Tuple[str, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _result = _data[2]
            logger.debug(
                "callback_query_data函数返回 result[%s] user_id[%s]",
                _result,
                _user_id,
            )
            return _result, _user_id

        try:
            pool_type, user_id = await get_wish_waiting_list_callback(callback_query.data)
        except IndexError:
            await callback_query.answer("按钮数据已过期，请重新获取。", show_alert=True)
            self.add_delete_message_job(message, delay=1)
            return
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        is_avatar = pool_type == "avatar"
        await self._get_wish_waiting_list(update, context, is_avatar)

    async def _get_wish_waiting_list(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE", is_avatar: bool) -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        user_id = user.id

        image = await self.render(user_id, is_avatar)
        reply_markup = await self.get_wish_waiting_list_button(user_id, is_avatar)
        if callback_query.message:
            await image.edit_media(callback_query.message, reply_markup=reply_markup)
        else:
            await image.edit_inline_media(callback_query, reply_markup=reply_markup)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        types = {"角色": "avatar", "武器": "weapon"}
        data = []
        for k, v in types.items():
            data.append(
                IInlineUseData(
                    text=f"未复刻列表 - {k}池",
                    hash=f"wish_waiting_list_{v}",
                    callback=partial(self._get_wish_waiting_list, is_avatar=v == "avatar"),
                )
            )
        return data
