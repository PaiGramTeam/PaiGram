"""幽境危战数据查询"""

import math
import re
from functools import lru_cache, partial
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from simnet import GenshinClient
from simnet.models.genshin.chronicle.hard_challenge import HardChallengeData
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters, ContextTypes

from core.plugin import Plugin, handler
from core.services.cookies.error import TooManyRequestPublicCookies
from core.services.history_data.models import HistoryDataHardChallenge
from core.services.history_data.services import HistoryDataHardChallengeServices
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from gram_core.config import config
from gram_core.dependence.redisdb import RedisDB
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from plugins.tools.genshin import GenshinHelper
from utils.enkanetwork import RedisCache
from utils.log import logger
from utils.uid import mask_number

TZ = ZoneInfo("Asia/Shanghai")

get_args_pattern = re.compile(r"\d+")


@lru_cache
def get_args(text: str) -> bool:
    return "pre" in text or "上期" in text


class AbyssUnlocked(Exception):
    """根本没动"""


class NoMostKills(Exception):
    """挑战了但是数据没刷新"""


class FloorNotFoundError(Exception):
    """只有数据统计，幕数统计未出"""


class AbyssNotFoundError(Exception):
    """如果查询别人，是无法找到队伍详细，只有数据统计"""


class HardChallengePlugin(Plugin):
    """幽境危战数据查询"""

    def __init__(
        self,
        template: TemplateService,
        helper: GenshinHelper,
        history_data_abyss: HistoryDataHardChallengeServices,
        redis: RedisDB,
    ):
        self.template_service = template
        self.helper = helper
        self.history_data_abyss = history_data_abyss
        self.cache = RedisCache(redis.client, key="plugin:hard_challenge:history")

    @handler.command("hard_challenge", block=False)
    @handler.message(filters.Regex(r"^幽境危战数据"), block=False)
    @handler.message(filters.Regex(r"^新新深渊数据"), block=False)
    @handler.message(filters.Regex(r"^三路深渊数据"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:  # skipcq: PY-R1000 #
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        args = self.get_args(context)
        message = update.effective_message

        # 若查询帮助
        if (message.text.startswith("/") and "help" in message.text) or "帮助" in message.text:
            await message.reply_text(
                "<b>幽境危战挑战数据</b>功能使用帮助（中括号表示可选参数）\n\n"
                "指令格式：\n<code>/hard_challenge + [pre]</code>\n（<code>pre</code>表示上期）\n\n"
                "文本格式：\n<code>幽境危战数据 + [上期]</code> \n\n"
                "例如以下指令都正确：\n"
                "<code>/hard_challenge</code>\n<code>/hard_challenge pre</code>\n"
                "<code>幽境危战数据查询</code>\n<code>幽境危战数据查询上期</code>",
                parse_mode=ParseMode.HTML,
            )
            self.log_user(update, logger.info, "查询[bold]幽境危战挑战数据[/bold]帮助", extra={"markup": True})
            return

        # 解析参数
        previous = get_args(" ".join([i for i in args if not i.startswith("@")]))

        self.log_user(
            update,
            logger.info,
            "[bold]幽境危战挑战数据[/bold]请求: previous=%s",
            previous,
            extra={"markup": True},
        )

        await message.reply_chat_action(ChatAction.TYPING)

        reply_text = await message.reply_text(f"{config.notice.bot_name}需要时间整理幽境危战数据，还请耐心等待哦~")
        try:
            async with self.helper.genshin_or_public(user_id, uid=uid, offset=offset) as client:
                if not client.public:
                    await client.get_record_cards()
                abyss_data = await self.get_rendered_pic_data(client, client.player_id, previous)
                images = await self.get_rendered_pic(abyss_data, client.player_id)
        except AbyssUnlocked:  # 若幽境危战未解锁
            await message.reply_text("还未解锁幽境危战哦~")
            return
        except NoMostKills:  # 若幽境危战还未挑战
            await message.reply_text("还没有挑战本次幽境危战呢，咕咕咕~")
            return
        except FloorNotFoundError:
            await message.reply_text("幽境危战详细数据未找到，咕咕咕~")
            return
        except AbyssNotFoundError:
            await message.reply_text("无法查询玩家挑战队伍详情，只能查询统计详情哦~")
            return
        except TooManyRequestPublicCookies:
            reply_message = await message.reply_text("查询次数太多，请您稍后重试")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message)
                self.add_delete_message_job(message)
            return
        finally:
            if reply_text is not None:
                await reply_text.delete()

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await images.reply_photo(message)

        self.log_user(update, logger.info, "[bold]幽境危战挑战数据[/bold]: 成功发送图片", extra={"markup": True})

    async def get_rendered_pic_data(self, client: GenshinClient, uid: int, previous: bool) -> "HardChallengeData":
        abyss_data = await client.get_genshin_hard_challenge(uid, need_detail=not client.public, lang="zh-cn")  # noqa
        if (not abyss_data.unlocked) or (not abyss_data.data):
            raise AbyssUnlocked
        index = 1 if previous else 0
        if len(abyss_data.data) <= index:
            raise AbyssUnlocked
        abyss_data = abyss_data.data[index]
        if not abyss_data.single.has_data or not abyss_data.schedule.is_valid:
            raise AbyssUnlocked
        if not client.public:  # noqa
            if len(abyss_data.single.challenge) > 0 and len(abyss_data.single.challenge[0].teams) > 0:
                await self.save_abyss_data(self.history_data_abyss, uid, abyss_data)
        return abyss_data

    async def get_rendered_pic(  # skipcq: PY-R1000 #
        self,
        abyss_data: "HardChallengeData",
        uid: int,
    ) -> RenderResult:
        """
        获取渲染后的图片

        Args:
            abyss_data (HardChallengeData): 幽境危战数据
            uid (int): 需要查询的 uid

        Returns:
            bytes格式的图片
        """

        if len(abyss_data.single.challenge) == 0:
            raise FloorNotFoundError
        if len(abyss_data.single.challenge[0].teams) == 0:
            raise AbyssNotFoundError

        start_time = abyss_data.schedule.start_time.strftime("%m月%d日 %H:%M")
        end_time = abyss_data.schedule.end_time.strftime("%m月%d日 %H:%M")

        render_data = {
            "title": "幽境危战",
            "start_time": start_time,
            "end_time": end_time,
            "uid": mask_number(uid),
            "abyss_data": abyss_data,
        }
        return await self.template_service.render(
            "genshin/hard_challenge/challenge.jinja2",
            render_data,
            viewport={"width": 1162, "height": 4000},
            query_selector=".container",
        )

    @staticmethod
    async def save_abyss_data(
        history_data_abyss: "HistoryDataHardChallengeServices",
        uid: int,
        abyss_data: "HardChallengeData",
    ) -> bool:
        model = history_data_abyss.create(uid, abyss_data)
        old_data = await history_data_abyss.get_by_user_id_data_id(uid, model.data_id)
        exists = history_data_abyss.exists_data(model, old_data)
        if not exists:
            await history_data_abyss.add(model)
            return True
        return False

    async def get_abyss_data(self, uid: int):
        return await self.history_data_abyss.get_by_user_id(uid)

    @staticmethod
    def get_season_data_name(data: "HistoryDataHardChallenge"):
        start_time = data.abyss_data.schedule.start_time.astimezone(TZ)
        time = start_time.strftime("%Y.%m ")[2:]
        difficulty = data.abyss_data.single.best.difficulty
        return f"{time} {data.abyss_data.schedule.name} ★ 难度{difficulty}"

    async def get_session_button_data(self, user_id: int, uid: int, force: bool = False):
        redis = await self.cache.get(str(uid))
        if redis and not force:
            return redis["buttons"]
        data = await self.get_abyss_data(uid)
        data.sort(key=lambda x: x.id, reverse=True)
        abyss_data = [HistoryDataHardChallenge.from_data(i) for i in data]
        buttons = [
            {
                "name": HardChallengePlugin.get_season_data_name(abyss_data[idx]),
                "value": f"get_hard_challenge_history|{user_id}|{uid}|{value.id}",
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
                    callback_data=f"get_hard_challenge_history|{user_id}|{uid}|p_{last_page}",
                )
            )
        if last_page or next_page:
            last_button.append(
                InlineKeyboardButton(
                    f"{page}/{all_page}",
                    callback_data=f"get_hard_challenge_history|{user_id}|{uid}|empty_data",
                )
            )
        if next_page:
            last_button.append(
                InlineKeyboardButton(
                    "下一页 >>",
                    callback_data=f"get_hard_challenge_history|{user_id}|{uid}|p_{next_page}",
                )
            )
        if last_button:
            send_buttons.append(last_button)
        return send_buttons

    @handler.command("hard_challenge_history", block=False)
    @handler.message(filters.Regex(r"^幽境危战历史数据"), block=False)
    async def abyss_history_command_start(self, update: Update, _: CallbackContext) -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        self.log_user(update, logger.info, "查询幽境危战历史数据")

        async with self.helper.genshin_or_public(user_id, uid=uid, offset=offset) as client:
            await self.get_session_button_data(user_id, client.player_id, force=True)
            buttons = await self.gen_season_button(user_id, client.player_id)
            if not buttons:
                await message.reply_text("还没有幽境危战历史数据哦~")
                return
        await message.reply_text("请选择要查询的幽境危战历史数据", reply_markup=InlineKeyboardMarkup(buttons))

    async def get_hard_challenge_history_page(self, update: "Update", user_id: int, uid: int, result: str):
        """翻页处理"""
        callback_query = update.callback_query

        self.log_user(update, logger.info, "切换幽境危战历史数据页 page[%s]", result)
        page = int(result.split("_")[1])
        async with self.helper.genshin_or_public(user_id, uid=uid) as client:
            buttons = await self.gen_season_button(user_id, client.player_id, page)
            if not buttons:
                await callback_query.answer("还没有幽境危战历史数据哦~", show_alert=True)
                await callback_query.edit_message_text("还没有幽境危战历史数据哦~")
                return
        await callback_query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer(f"已切换到第 {page} 页", show_alert=False)

    async def get_hard_challenge_history_floor(self, update: "Update", data_id: int):
        """渲染幕数数据"""
        callback_query = update.callback_query
        message = callback_query.message
        reply = None
        if message.reply_to_message:
            reply = message.reply_to_message

        data = await self.history_data_abyss.get_by_id(data_id)
        if not data:
            await callback_query.answer("数据不存在，请尝试重新发送命令", show_alert=True)
            await callback_query.edit_message_text("数据不存在，请尝试重新发送命令~")
            return
        abyss_data = HistoryDataHardChallenge.from_data(data)

        images = await self.get_rendered_pic(abyss_data.abyss_data, data.user_id)
        await callback_query.answer("正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        await images.reply_photo(reply or message)
        self.log_user(update, logger.info, "[bold]幽境危战挑战数据[/bold]: 成功发送图片", extra={"markup": True})
        self.add_delete_message_job(message, delay=1)

    @handler.callback_query(pattern=r"^get_hard_challenge_history\|", block=False)
    async def get_hard_challenge_history(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        async def get_hard_challenge_history_callback(
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

        result, user_id, uid = await get_hard_challenge_history_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        if result == "empty_data":
            await callback_query.answer(text="此按钮不可用", show_alert=True)
            return
        if result.startswith("p_"):
            await self.get_hard_challenge_history_page(update, user_id, uid, result)
            return
        data_id = int(result)
        await self.get_hard_challenge_history_floor(update, data_id)

    async def abyss_use_by_inline(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE", previous: bool):
        callback_query = update.callback_query
        user = update.effective_user
        user_id = user.id
        uid = IInlineUseData.get_uid_from_context(context)

        self.log_user(update, logger.info, "查询幽境危战挑战总览数据 previous[%s]", previous)
        notice = None
        try:
            async with self.helper.genshin_or_public(user_id, uid=uid) as client:
                if not client.public:
                    await client.get_record_cards()
                abyss_data = await self.get_rendered_pic_data(client, client.player_id, previous)
                image = await self.get_rendered_pic(abyss_data, client.player_id)
        except AbyssUnlocked:  # 若幽境危战未解锁
            notice = "还未解锁幽境危战哦~"
        except NoMostKills:  # 若幽境危战还未挑战
            notice = "还没有挑战本次幽境危战呢，咕咕咕~"
        except AbyssNotFoundError:
            notice = "无法查询玩家挑战队伍详情，只能查询统计详情哦~"
        except TooManyRequestPublicCookies:
            notice = "查询次数太多，请您稍后重试"

        if notice:
            await callback_query.answer(notice, show_alert=True)
            return

        await image.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        return [
            IInlineUseData(
                text="本期幽境危战挑战总览",
                hash="hard_challenge_current",
                callback=partial(self.abyss_use_by_inline, previous=False),
                player=True,
            ),
            IInlineUseData(
                text="上期幽境危战挑战总览",
                hash="hard_challenge_previous",
                callback=partial(self.abyss_use_by_inline, previous=True),
                player=True,
            ),
        ]
