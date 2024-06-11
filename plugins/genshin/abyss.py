"""深渊数据查询"""

import asyncio
import math
import re
from datetime import datetime
from functools import lru_cache
from typing import Any, Coroutine, List, Optional, Tuple, Union, Dict

from arkowrapper import ArkoWrapper
from pytz import timezone
from simnet import GenshinClient
from simnet.models.genshin.chronicle.abyss import SpiralAbyss
from telegram import Message, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters, ContextTypes

from core.dependence.assets import AssetsService
from core.plugin import Plugin, handler
from core.services.cookies.error import TooManyRequestPublicCookies
from core.services.history_data.models import HistoryDataAbyss
from core.services.history_data.services import HistoryDataAbyssServices
from core.services.template.models import RenderGroupResult, RenderResult
from core.services.template.services import TemplateService
from gram_core.config import config
from gram_core.dependence.redisdb import RedisDB
from plugins.tools.genshin import GenshinHelper
from utils.enkanetwork import RedisCache
from utils.log import logger
from utils.uid import mask_number

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

TZ = timezone("Asia/Shanghai")

get_args_pattern = re.compile(r"\d+")


@lru_cache
def get_args(text: str) -> Tuple[int, bool, bool]:
    total = "all" in text or "总览" in text
    prev = "pre" in text or "上期" in text
    floor = 0

    if not total:
        m = get_args_pattern.search(text)
        if m is not None:
            floor = int(m.group(0))

    return floor, total, prev


class AbyssUnlocked(Exception):
    """根本没动"""


class NoMostKills(Exception):
    """挑战了但是数据没刷新"""


class FloorNotFoundError(Exception):
    """只有数据统计，层数统计未出"""


class AbyssNotFoundError(Exception):
    """如果查询别人，是无法找到队伍详细，只有数据统计"""


class AbyssPlugin(Plugin):
    """深渊数据查询"""

    def __init__(
        self,
        template: TemplateService,
        helper: GenshinHelper,
        assets_service: AssetsService,
        history_data_abyss: HistoryDataAbyssServices,
        redis: RedisDB,
    ):
        self.template_service = template
        self.helper = helper
        self.assets_service = assets_service
        self.history_data_abyss = history_data_abyss
        self.cache = RedisCache(redis.client, key="plugin:abyss:history")

    @handler.command("abyss", block=False)
    @handler.message(filters.Regex(r"^深渊数据"), block=False)
    async def command_start(self, update: Update, _: CallbackContext) -> None:  # skipcq: PY-R1000 #
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message

        # 若查询帮助
        if (message.text.startswith("/") and "help" in message.text) or "帮助" in message.text:
            await message.reply_text(
                "<b>深渊挑战数据</b>功能使用帮助（中括号表示可选参数）\n\n"
                "指令格式：\n<code>/abyss + [层数/all] + [pre]</code>\n（<code>pre</code>表示上期）\n\n"
                "文本格式：\n<code>深渊数据 + 查询/总览 + [上期] + [层数]</code> \n\n"
                "例如以下指令都正确：\n"
                "<code>/abyss</code>\n<code>/abyss 12 pre</code>\n<code>/abyss all pre</code>\n"
                "<code>深渊数据查询</code>\n<code>深渊数据查询上期第12层</code>\n<code>深渊数据总览上期</code>",
                parse_mode=ParseMode.HTML,
            )
            self.log_user(update, logger.info, "查询[bold]深渊挑战数据[/bold]帮助", extra={"markup": True})
            return

        # 解析参数
        floor, total, previous = get_args(message.text)

        if floor > 12 or floor < 0:
            reply_msg = await message.reply_text("深渊层数输入错误，请重新输入。支持的参数为： 1-12 或 all")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_msg)
                self.add_delete_message_job(message)
            return
        if 0 < floor < 9:
            previous = False

        self.log_user(
            update,
            logger.info,
            "[bold]深渊挑战数据[/bold]请求: floor=%s total=%s previous=%s",
            floor,
            total,
            previous,
            extra={"markup": True},
        )

        await message.reply_chat_action(ChatAction.TYPING)

        reply_text: Optional[Message] = None

        if total:
            reply_text = await message.reply_text(f"{config.notice.bot_name}需要时间整理深渊数据，还请耐心等待哦~")
        try:
            async with self.helper.genshin_or_public(user_id, uid=uid, offset=offset) as client:
                if not client.public:
                    await client.get_record_cards()
                abyss_data, avatar_data = await self.get_rendered_pic_data(client, client.player_id, previous)
                images = await self.get_rendered_pic(abyss_data, avatar_data, client.player_id, floor, total)
        except AbyssUnlocked:  # 若深渊未解锁
            await message.reply_text("还未解锁深渊哦~")
            return
        except NoMostKills:  # 若深渊还未挑战
            await message.reply_text("还没有挑战本次深渊呢，咕咕咕~")
            return
        except FloorNotFoundError:
            await message.reply_text("深渊详细数据未找到，咕咕咕~")
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

        if images is None:
            await message.reply_text(f"还没有第 {floor} 层的挑战数据")
            return

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        for group in ArkoWrapper(images).group(10):  # 每 10 张图片分一个组
            await RenderGroupResult(results=group).reply_media_group(message, write_timeout=60)

        self.log_user(update, logger.info, "[bold]深渊挑战数据[/bold]: 成功发送图片", extra={"markup": True})

    async def get_rendered_pic_data(
        self, client: GenshinClient, uid: int, previous: bool
    ) -> Tuple["SpiralAbyss", Dict[int, int]]:
        abyss_data = await client.get_genshin_spiral_abyss(uid, previous=previous, lang="zh-cn")
        avatar_data = {}
        if not client.public:  # noqa
            avatars = await client.get_genshin_characters(uid, lang="zh-cn")
            avatar_data = {i.id: i.constellation for i in avatars}
            if abyss_data.unlocked and abyss_data.ranks.most_kills:
                await self.save_abyss_data(self.history_data_abyss, uid, abyss_data, avatar_data)
        return abyss_data, avatar_data

    async def get_rendered_pic(  # skipcq: PY-R1000 #
        self, abyss_data: "SpiralAbyss", avatar_data: Dict[int, int], uid: int, floor: int, total: bool
    ) -> Union[Tuple[Any], List[RenderResult], None]:
        """
        获取渲染后的图片

        Args:
            abyss_data (SpiralAbyss): 深渊数据
            avatar_data (Dict[int, int]): 角色数据
            uid (int): 需要查询的 uid
            floor (int): 层数
            total (bool): 是否为总览

        Returns:
            bytes格式的图片
        """

        def json_encoder(value):
            if isinstance(value, datetime):
                return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S")
            return value

        if not abyss_data.unlocked:
            raise AbyssUnlocked
        if not abyss_data.ranks.most_kills:
            raise NoMostKills
        if (total or (floor > 0)) and len(abyss_data.floors) == 0:
            raise FloorNotFoundError
        if (total or (floor > 0)) and len(abyss_data.floors[0].chambers[0].battles) == 0:
            raise AbyssNotFoundError

        start_time = abyss_data.start_time.astimezone(TZ)
        time = start_time.strftime("%Y年%m月") + ("上" if start_time.day <= 15 else "下")
        stars = [i.stars for i in filter(lambda x: x.floor > 8, abyss_data.floors)]
        total_stars = f"{sum(stars)} ({'-'.join(map(str, stars))})"

        render_data = {}
        result = abyss_data.json(encoder=json_encoder)

        render_data["time"] = time
        render_data["stars"] = total_stars
        render_data["uid"] = mask_number(uid)
        render_data["floor_colors"] = {
            1: "#374952",
            2: "#374952",
            3: "#55464B",
            4: "#55464B",
            5: "#55464B",
            6: "#1D2A5D",
            7: "#1D2A5D",
            8: "#1D2A5D",
            9: "#292B58",
            10: "#382024",
            11: "#252550",
            12: "#1D2A4A",
        }

        if total:
            render_data["avatar_data"] = avatar_data
            data = jsonlib.loads(result)
            render_data["data"] = data

            render_inputs: List[Tuple[int, Coroutine[Any, Any, RenderResult]]] = []

            def overview_task():
                return -1, self.template_service.render(
                    "genshin/abyss/overview.jinja2", render_data, viewport={"width": 750, "height": 580}
                )

            def floor_task(floor_index: int):
                floor_d = data["floors"][floor_index]
                return (
                    floor_d["floor"],
                    self.template_service.render(
                        "genshin/abyss/floor.jinja2",
                        {
                            **render_data,
                            "floor": floor_d,
                            "total_stars": f"{floor_d['stars']}/{floor_d['max_stars']}",
                        },
                        viewport={"width": 690, "height": 500},
                        full_page=True,
                        ttl=15 * 24 * 60 * 60,
                    ),
                )

            render_inputs.append(overview_task())

            for i, f in enumerate(data["floors"]):
                if f["floor"] >= 9:
                    render_inputs.append(floor_task(i))

            render_group_inputs = list(map(lambda x: x[1], sorted(render_inputs, key=lambda x: x[0])))

            return await asyncio.gather(*render_group_inputs)

        if floor < 1:
            render_data["data"] = jsonlib.loads(result)
            return [
                await self.template_service.render(
                    "genshin/abyss/overview.jinja2", render_data, viewport={"width": 750, "height": 580}
                )
            ]
        num_dic = {
            "0": "",
            "1": "一",
            "2": "二",
            "3": "三",
            "4": "四",
            "5": "五",
            "6": "六",
            "7": "七",
            "8": "八",
            "9": "九",
        }
        if num := num_dic.get(str(floor)):
            render_data["floor-num"] = num
        else:
            render_data["floor-num"] = f"十{num_dic.get(str(floor % 10))}"
        floors = jsonlib.loads(result)["floors"]
        if not (floor_data := list(filter(lambda x: x["floor"] == floor, floors))):
            return None
        render_data["avatar_data"] = avatar_data
        render_data["floor"] = floor_data[0]
        render_data["total_stars"] = f"{floor_data[0]['stars']}/{floor_data[0]['max_stars']}"
        return [
            await self.template_service.render(
                "genshin/abyss/floor.jinja2", render_data, viewport={"width": 690, "height": 500}
            )
        ]

    @staticmethod
    async def save_abyss_data(
        history_data_abyss: "HistoryDataAbyssServices",
        uid: int,
        abyss_data: "SpiralAbyss",
        character_data: Dict[int, int],
    ) -> bool:
        model = history_data_abyss.create(uid, abyss_data, character_data)
        old_data = await history_data_abyss.get_by_user_id_data_id(uid, model.data_id)
        exists = history_data_abyss.exists_data(model, old_data)
        if not exists:
            await history_data_abyss.add(model)
            return True
        return False

    async def get_abyss_data(self, uid: int):
        return await self.history_data_abyss.get_by_user_id(uid)

    @staticmethod
    def get_season_data_name(data: "HistoryDataAbyss"):
        start_time = data.abyss_data.start_time.astimezone(TZ)
        time = start_time.strftime("%Y.%m ")[2:] + ("上" if start_time.day <= 15 else "下")
        honor = ""
        if data.abyss_data.total_stars == 36:
            if data.abyss_data.total_battles == 12:
                honor = "👑"
            last_battles = data.abyss_data.floors[-1].chambers[-1].battles
            num_of_characters = max(
                len(last_battles[0].characters),
                len(last_battles[1].characters),
            )
            if num_of_characters == 2:
                honor = "双通"
            elif num_of_characters == 1:
                honor = "单通"

        return f"{time} {data.abyss_data.total_stars} ★ {honor}"

    async def get_session_button_data(self, user_id: int, uid: int, force: bool = False):
        redis = await self.cache.get(str(uid))
        if redis and not force:
            return redis["buttons"]
        data = await self.get_abyss_data(uid)
        data.sort(key=lambda x: x.id, reverse=True)
        abyss_data = [HistoryDataAbyss.from_data(i) for i in data]
        buttons = [
            {
                "name": AbyssPlugin.get_season_data_name(abyss_data[idx]),
                "value": f"get_abyss_history|{user_id}|{uid}|{value.id}",
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
                    callback_data=f"get_abyss_history|{user_id}|{uid}|p_{last_page}",
                )
            )
        if last_page or next_page:
            last_button.append(
                InlineKeyboardButton(
                    f"{page}/{all_page}",
                    callback_data=f"get_abyss_history|{user_id}|{uid}|empty_data",
                )
            )
        if next_page:
            last_button.append(
                InlineKeyboardButton(
                    "下一页 >>",
                    callback_data=f"get_abyss_history|{user_id}|{uid}|p_{next_page}",
                )
            )
        if last_button:
            send_buttons.append(last_button)
        return send_buttons

    @staticmethod
    async def gen_floor_button(
        data_id: int,
        abyss_data: "HistoryDataAbyss",
        user_id: int,
        uid: int,
    ) -> List[List[InlineKeyboardButton]]:
        floors = [i.floor for i in abyss_data.abyss_data.floors if i.floor]
        floors.sort()
        buttons = [
            InlineKeyboardButton(
                f"第 {i} 层",
                callback_data=f"get_abyss_history|{user_id}|{uid}|{data_id}|{i}",
            )
            for i in floors
        ]
        send_buttons = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
        all_buttons = [
            InlineKeyboardButton(
                "<< 返回",
                callback_data=f"get_abyss_history|{user_id}|{uid}|p_1",
            ),
            InlineKeyboardButton(
                "总览",
                callback_data=f"get_abyss_history|{user_id}|{uid}|{data_id}|total",
            ),
            InlineKeyboardButton(
                "所有",
                callback_data=f"get_abyss_history|{user_id}|{uid}|{data_id}|all",
            ),
        ]
        send_buttons.append(all_buttons)
        return send_buttons

    @handler.command("abyss_history", block=False)
    @handler.message(filters.Regex(r"^深渊历史数据"), block=False)
    async def abyss_history_command_start(self, update: Update, _: CallbackContext) -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        self.log_user(update, logger.info, "查询深渊历史数据")

        async with self.helper.genshin_or_public(user_id, uid=uid, offset=offset) as client:
            await self.get_session_button_data(user_id, client.player_id, force=True)
            buttons = await self.gen_season_button(user_id, client.player_id)
            if not buttons:
                await message.reply_text("还没有深渊历史数据哦~")
                return
        await message.reply_text("请选择要查询的深渊历史数据", reply_markup=InlineKeyboardMarkup(buttons))

    async def get_abyss_history_page(self, update: "Update", user_id: int, uid: int, result: str):
        """翻页处理"""
        callback_query = update.callback_query

        self.log_user(update, logger.info, "切换深渊历史数据页 page[%s]", result)
        page = int(result.split("_")[1])
        async with self.helper.genshin_or_public(user_id, uid=uid) as client:
            buttons = await self.gen_season_button(user_id, client.player_id, page)
            if not buttons:
                await callback_query.answer("还没有深渊历史数据哦~", show_alert=True)
                await callback_query.edit_message_text("还没有深渊历史数据哦~")
                return
        await callback_query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer(f"已切换到第 {page} 页", show_alert=False)

    async def get_abyss_history_season(self, update: "Update", data_id: int):
        """进入选择层数"""
        callback_query = update.callback_query
        user = callback_query.from_user

        self.log_user(update, logger.info, "切换深渊历史数据到层数页 data_id[%s]", data_id)
        data = await self.history_data_abyss.get_by_id(data_id)
        if not data:
            await callback_query.answer("数据不存在，请尝试重新发送命令~", show_alert=True)
            await callback_query.edit_message_text("数据不存在，请尝试重新发送命令~")
            return
        abyss_data = HistoryDataAbyss.from_data(data)
        buttons = await self.gen_floor_button(data_id, abyss_data, user.id, data.user_id)
        await callback_query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
        await callback_query.answer("已切换到层数页", show_alert=False)

    async def get_abyss_history_floor(self, update: "Update", data_id: int, detail: str):
        """渲染层数数据"""
        callback_query = update.callback_query
        message = callback_query.message
        reply = None
        if message.reply_to_message:
            reply = message.reply_to_message

        floor = 0
        total = False
        if detail == "total":
            floor = 0
        elif detail == "all":
            total = True
        else:
            floor = int(detail)
        data = await self.history_data_abyss.get_by_id(data_id)
        if not data:
            await callback_query.answer("数据不存在，请尝试重新发送命令", show_alert=True)
            await callback_query.edit_message_text("数据不存在，请尝试重新发送命令~")
            return
        abyss_data = HistoryDataAbyss.from_data(data)

        images = await self.get_rendered_pic(
            abyss_data.abyss_data, abyss_data.character_data, data.user_id, floor, total
        )
        if images is None:
            await callback_query.answer(f"还没有第 {floor} 层的挑战数据", show_alert=True)
            return
        await callback_query.answer("正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        for group in ArkoWrapper(images).group(10):  # 每 10 张图片分一个组
            await RenderGroupResult(results=group).reply_media_group(reply or message, write_timeout=60)
        self.log_user(update, logger.info, "[bold]深渊挑战数据[/bold]: 成功发送图片", extra={"markup": True})
        self.add_delete_message_job(message, delay=1)

    @handler.callback_query(pattern=r"^get_abyss_history\|", block=False)
    async def get_abyss_history(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        async def get_abyss_history_callback(
            callback_query_data: str,
        ) -> Tuple[str, str, int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            _result = _data[3]
            _detail = _data[4] if len(_data) > 4 else None
            logger.debug(
                "callback_query_data函数返回 detail[%s] result[%s] user_id[%s] uid[%s]",
                _detail,
                _result,
                _user_id,
                _uid,
            )
            return _detail, _result, _user_id, _uid

        detail, result, user_id, uid = await get_abyss_history_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        if result == "empty_data":
            await callback_query.answer(text="此按钮不可用", show_alert=True)
            return
        if result.startswith("p_"):
            await self.get_abyss_history_page(update, user_id, uid, result)
            return
        data_id = int(result)
        if detail:
            await self.get_abyss_history_floor(update, data_id, detail)
            return
        await self.get_abyss_history_season(update, data_id)
