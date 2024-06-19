import math
import os
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Tuple, Optional

from simnet.errors import DataNotPublic, BadRequest as SimnetBadRequest
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import filters

from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.history_data.models import HistoryDataLedger
from core.services.history_data.services import HistoryDataLedgerServices
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from gram_core.config import config
from gram_core.dependence.redisdb import RedisDB
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from plugins.tools.genshin import GenshinHelper
from utils.enkanetwork import RedisCache
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from simnet import GenshinClient
    from simnet.models.genshin.diary import Diary

__all__ = ("LedgerPlugin",)


class LedgerPlugin(Plugin):
    """旅行札记查询"""

    def __init__(
        self,
        helper: GenshinHelper,
        cookies_service: CookiesService,
        template_service: TemplateService,
        history_data_ledger: HistoryDataLedgerServices,
        redis: RedisDB,
    ):
        self.template_service = template_service
        self.cookies_service = cookies_service
        self.current_dir = os.getcwd()
        self.helper = helper
        self.history_data_ledger = history_data_ledger
        self.cache = RedisCache(redis.client, key="plugin:ledger:history")
        self.kitsune = None

    async def _start_get_ledger(self, client: "GenshinClient", month=None) -> RenderResult:
        diary_info = await client.get_genshin_diary(client.player_id, month=month)
        if month:
            await self.save_ledger_data(self.history_data_ledger, client.player_id, diary_info)
        return await self._start_get_ledger_render(client.player_id, diary_info)

    async def _start_get_ledger_render(self, uid: int, diary_info: "Diary") -> RenderResult:
        color = ["#73a9c6", "#d56565", "#70b2b4", "#bd9a5a", "#739970", "#7a6da7", "#597ea0"]
        categories = [
            {
                "id": i.id,
                "name": i.name,
                "color": color[i.id % len(color)],
                "amount": i.amount,
                "percentage": i.percentage,
            }
            for i in diary_info.month_data.categories
        ]
        color = [i["color"] for i in categories]

        def format_amount(amount: int) -> str:
            return f"{round(amount / 10000, 2)}w" if amount >= 10000 else amount

        ledger_data = {
            "uid": mask_number(uid),
            "day": diary_info.month,
            "current_primogems": format_amount(diary_info.month_data.current_primogems),
            "gacha": int(diary_info.month_data.current_primogems / 160),
            "current_mora": format_amount(diary_info.month_data.current_mora),
            "last_primogems": format_amount(diary_info.month_data.last_primogems),
            "last_gacha": int(diary_info.month_data.last_primogems / 160),
            "last_mora": format_amount(diary_info.month_data.last_mora),
            "categories": categories,
            "color": color,
        }
        render_result = await self.template_service.render(
            "genshin/ledger/ledger.jinja2", ledger_data, {"width": 580, "height": 610}
        )
        return render_result

    @handler.command(command="ledger", cookie=True, block=False)
    @handler.message(filters=filters.Regex("^旅行札记查询(.*)"), block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message

        now = datetime.now()
        now_time = (now - timedelta(days=1)) if now.day == 1 and now.hour <= 4 else now
        month = now_time.month
        try:
            args = self.get_args(context)
            if len(args) >= 1:
                month = args[0].replace("月", "")
            if re_data := re.findall(r"\d+", str(month)):
                month = int(re_data[0])
            else:
                num_dict = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                month = sum(num_dict.get(i, 0) for i in str(month))
            # check right
            allow_month = [now_time.month]

            last_month = now_time.replace(day=1) - timedelta(days=1)
            allow_month.append(last_month.month)

            last_month = last_month.replace(day=1) - timedelta(days=1)
            allow_month.append(last_month.month)

            if month not in allow_month and isinstance(month, int):
                raise IndexError
        except IndexError:
            reply_message = await message.reply_text("仅可查询最新三月的数据，请重新输入")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return
        self.log_user(update, logger.info, "查询旅行札记")
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            async with self.helper.genshin(user_id, player_id=uid, offset=offset) as client:
                render_result = await self._start_get_ledger(client, month)
        except DataNotPublic:
            reply_message = await message.reply_text(
                "查询失败惹，可能是旅行札记功能被禁用了？请先通过米游社或者 hoyolab 获取一次旅行札记后重试。"
            )
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return
        except SimnetBadRequest as exc:
            if exc.ret_code == -120:
                await message.reply_text("当前角色冒险等阶不足，暂时无法获取信息")
                return
            raise exc
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename=f"{client.player_id}.png")

    @staticmethod
    async def save_ledger_data(
        history_data_ledger: "HistoryDataLedgerServices", uid: int, ledger_data: "Diary"
    ) -> bool:
        month = int((ledger_data.date or datetime.now().strftime("%Y-%m-%d")).split("-")[1])
        if month == ledger_data.month:
            return False
        model = history_data_ledger.create(uid, ledger_data)
        old_data = await history_data_ledger.get_by_user_id_data_id(uid, model.data_id)
        if not old_data:
            await history_data_ledger.add(model)
            return True
        return False

    async def get_ledger_data(self, uid: int):
        return await self.history_data_ledger.get_by_user_id(uid)

    @staticmethod
    def get_season_data_name(data: "HistoryDataLedger") -> str:
        return f"{data.diary_data.data_id}"

    async def get_session_button_data(self, user_id: int, uid: int, force: bool = False):
        redis = await self.cache.get(str(uid))
        if redis and not force:
            return redis["buttons"]
        data = await self.get_ledger_data(uid)
        data.sort(key=lambda x: x.data_id, reverse=True)
        abyss_data = [HistoryDataLedger.from_data(i) for i in data]
        buttons = [
            {
                "name": LedgerPlugin.get_season_data_name(abyss_data[idx]),
                "value": f"get_ledger_history|{user_id}|{uid}|{value.id}",
            }
            for idx, value in enumerate(data)
        ]
        await self.cache.set(str(uid), {"buttons": buttons})
        return buttons

    async def gen_season_button(
        self,
        user_id: int,
        uid: int,
        page: int = 1,
    ) -> List[List[InlineKeyboardButton]]:
        """生成按钮"""
        data = await self.get_session_button_data(user_id, uid)
        if not data:
            return []
        buttons = [
            InlineKeyboardButton(
                value["name"],
                callback_data=value["value"],
            )
            for value in data
        ]
        all_buttons = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
        send_buttons = all_buttons[(page - 1) * 5 : page * 5]
        last_page = page - 1 if page > 1 else 0
        all_page = math.ceil(len(all_buttons) / 5)
        next_page = page + 1 if page < all_page and all_page > 1 else 0
        last_button = []
        if last_page:
            last_button.append(
                InlineKeyboardButton(
                    "<< 上一页",
                    callback_data=f"get_ledger_history|{user_id}|{uid}|p_{last_page}",
                )
            )
        if last_page or next_page:
            last_button.append(
                InlineKeyboardButton(
                    f"{page}/{all_page}",
                    callback_data=f"get_ledger_history|{user_id}|{uid}|empty_data",
                )
            )
        if next_page:
            last_button.append(
                InlineKeyboardButton(
                    "下一页 >>",
                    callback_data=f"get_ledger_history|{user_id}|{uid}|p_{next_page}",
                )
            )
        if last_button:
            send_buttons.append(last_button)
        return send_buttons

    @handler.command("ledger_history", block=False)
    @handler.message(filters.Regex(r"^旅行札记历史数据"), block=False)
    async def ledger_history_command_start(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        self.log_user(update, logger.info, "查询旅行札记历史数据")

        async with self.helper.genshin(user_id, player_id=uid, offset=offset) as client:
            await self.get_session_button_data(user_id, client.player_id, force=True)
            buttons = await self.gen_season_button(user_id, client.player_id)
            if not buttons:
                await message.reply_text("还没有旅行札记历史数据哦~")
                return
        if isinstance(self.kitsune, str):
            photo = self.kitsune
        else:
            photo = open("resources/img/kitsune.png", "rb")
        reply_message = await message.reply_photo(
            photo, "请选择要查询的旅行札记历史数据", reply_markup=InlineKeyboardMarkup(buttons)
        )
        if reply_message.photo:
            self.kitsune = reply_message.photo[-1].file_id

    async def get_ledger_history_page(self, update: "Update", user_id: int, uid: int, result: str):
        """翻页处理"""
        callback_query = update.callback_query

        self.log_user(update, logger.info, "切换旅行札记历史数据页 page[%s]", result)
        page = int(result.split("_")[1])
        async with self.helper.genshin(user_id, player_id=uid) as client:
            buttons = await self.gen_season_button(user_id, client.player_id, page)
            if not buttons:
                await callback_query.answer("还没有旅行札记历史数据哦~", show_alert=True)
                await callback_query.edit_message_text("还没有旅行札记历史数据哦~")
                return
        await callback_query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer(f"已切换到第 {page} 页", show_alert=False)

    @handler.callback_query(pattern=r"^get_ledger_history\|", block=False)
    async def get_ledger_history(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        message = callback_query.message
        user = callback_query.from_user

        async def get_ledger_history_callback(
            callback_query_data: str,
        ) -> Tuple[str, int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            _result = _data[3]
            logger.debug(
                "callback_query_data函数返回 result[%s] user_id[%s] uid[%s]",
                _result,
                _user_id,
                _uid,
            )
            return _result, _user_id, _uid

        result, user_id, uid = await get_ledger_history_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        if result == "empty_data":
            await callback_query.answer(text="此按钮不可用", show_alert=True)
            return
        if result.startswith("p_"):
            await self.get_ledger_history_page(update, user_id, uid, result)
            return
        data_id = int(result)
        data = await self.history_data_ledger.get_by_id(data_id)
        if not data:
            await callback_query.answer("数据不存在，请尝试重新发送命令", show_alert=True)
            await callback_query.edit_message_text("数据不存在，请尝试重新发送命令~")
            return
        await callback_query.answer("正在渲染图片中 请稍等 请不要重复点击按钮")
        render = await self._start_get_ledger_render(user_id, HistoryDataLedger.from_data(data).diary_data)
        await render.edit_media(message)

    async def ledger_use_by_inline(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        callback_query = update.callback_query
        user = update.effective_user
        user_id = user.id
        uid = IInlineUseData.get_uid_from_context(context)

        self.log_user(update, logger.info, "查询旅行札记")
        try:
            async with self.helper.genshin(user_id, player_id=uid) as client:
                render_result = await self._start_get_ledger(client)
        except DataNotPublic:
            await callback_query.answer(
                "查询失败惹，可能是旅行札记功能被禁用了？请先通过米游社或者 hoyolab 获取一次旅行札记后重试。",
                show_alert=True,
            )
            return
        except SimnetBadRequest as exc:
            if exc.ret_code == -120:
                await callback_query.answer(
                    "当前角色冒险等阶不足，暂时无法获取信息",
                    show_alert=True,
                )
                return
            raise exc

        await render_result.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        return [
            IInlineUseData(
                text="当月旅行札记",
                hash="ledger",
                callback=self.ledger_use_by_inline,
                cookie=True,
                player=True,
            )
        ]
