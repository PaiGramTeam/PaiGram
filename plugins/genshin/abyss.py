"""深渊数据查询"""
import asyncio
import re
from datetime import datetime
from functools import lru_cache, partial
from typing import Any, Coroutine, List, Match, Optional, Tuple, Union

from arkowrapper import ArkoWrapper
from genshin import Client, GenshinException
from pytz import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters
from telegram.helpers import create_deep_linked_url

from core.dependence.assets import AssetsService
from core.plugin import Plugin, handler
from core.services.cookies.error import TooManyRequestPublicCookies
from core.services.template.models import RenderGroupResult, RenderResult
from core.services.template.services import TemplateService
from metadata.genshin import game_id_to_role_id
from plugins.tools.genshin import GenshinHelper, CookiesNotFoundError, PlayerNotFoundError
from utils.helpers import async_re_sub
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


TZ = timezone("Asia/Shanghai")
cmd_pattern = r"(?i)^/abyss\s*((?:\d+)|(?:all))?\s*(pre)?"
msg_pattern = r"^深渊数据((?:查询)|(?:总览))(上期)?\D?(\d*)?.*?$"

regex_01 = r"['\"]icon['\"]:\s*['\"](.*?)['\"]"
regex_02 = r"['\"]side_icon['\"]:\s*['\"](.*?)['\"]"


async def replace_01(match: Match, assets_service: AssetsService) -> str:
    aid = game_id_to_role_id(re.findall(r"UI_AvatarIcon_(.*?).png", match.group(1))[0])
    return (await assets_service.avatar(aid).icon()).as_uri()


async def replace_02(match: Match, assets_service: AssetsService) -> str:
    aid = game_id_to_role_id(re.findall(r"UI_AvatarIcon_Side_(.*?).png", match.group(1))[0])
    return (await assets_service.avatar(aid).side()).as_uri()


@lru_cache
def get_args(text: str) -> Tuple[int, bool, bool]:
    if text.startswith("/"):
        result = re.match(cmd_pattern, text).groups()
        try:
            floor = int(result[0] or 0)
        except ValueError:
            floor = 0
        return floor, result[0] == "all", bool(result[1])
    result = re.match(msg_pattern, text).groups()
    return int(result[2] or 0), result[0] == "总览", result[1] == "上期"


class AbyssUnlocked(Exception):
    """根本没动"""


class NoMostKills(Exception):
    """挑战了但是数据没刷新"""


class AbyssNotFoundError(Exception):
    """如果查询别人，是无法找到队伍详细，只有数据统计"""


class AbyssPlugin(Plugin):
    """深渊数据查询"""

    def __init__(
        self,
        template: TemplateService,
        helper: GenshinHelper,
        assets_service: AssetsService,
    ):
        self.template_service = template
        self.helper = helper
        self.assets_service = assets_service

    @handler.command("abyss", block=False)
    @handler.message(filters.Regex(msg_pattern), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        uid: Optional[int] = None

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
            logger.info("用户 %s[%s] 查询[bold]深渊挑战数据[/bold]帮助", user.full_name, user.id, extra={"markup": True})
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

        logger.info(
            "用户 %s[%s] [bold]深渊挑战数据[/bold]请求: floor=%s total=%s previous=%s",
            user.full_name,
            user.id,
            floor,
            total,
            previous,
            extra={"markup": True},
        )

        try:
            try:
                client = await self.helper.get_genshin_client(user.id)
                await client.get_record_cards()
                uid = client.uid
            except CookiesNotFoundError:
                client, uid = await self.helper.get_public_genshin_client(user.id)
        except PlayerNotFoundError:  # 若未找到账号
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_uid"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self.add_delete_message_job(reply_message)
                self.add_delete_message_job(message)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
            return
        except TooManyRequestPublicCookies:
            reply_message = await message.reply_text("查询次数太多，请您稍后重试")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message)
                self.add_delete_message_job(message)
            return

        async def reply_message_func(content: str) -> None:
            _user = await client.get_genshin_user(uid)
            _reply_msg = await message.reply_text(
                f"旅行者 {_user.info.nickname}(<code>{uid}</code>) {content}", parse_mode=ParseMode.HTML
            )

        reply_text: Optional[Message] = None

        if total:
            reply_text = await message.reply_text("派蒙需要时间整理深渊数据，还请耐心等待哦~")

        await message.reply_chat_action(ChatAction.TYPING)

        try:
            images = await self.get_rendered_pic(client, uid, floor, total, previous)
        except GenshinException as exc:
            if exc.retcode == 1034 and client.uid != uid:
                await message.reply_text("出错了呜呜呜 ~ 请稍后重试")
                return
            raise exc
        except AbyssUnlocked:  # 若深渊未解锁
            await reply_message_func("还未解锁深渊哦~")
            return
        except NoMostKills:  # 若深渊还未挑战
            await reply_message_func("还没有挑战本次深渊呢，咕咕咕~")
            return
        except AbyssNotFoundError:
            await reply_message_func("无法查询玩家挑战队伍详情，只能查询统计详情哦~")
            return
        except IndexError:  # 若深渊为挑战此层
            await reply_message_func("还没有挑战本层呢，咕咕咕~")
            return
        if images is None:
            await reply_message_func(f"还没有第 {floor} 层的挑战数据")
            return

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        for group in ArkoWrapper(images).group(10):  # 每 10 张图片分一个组
            await RenderGroupResult(results=group).reply_media_group(
                message, allow_sending_without_reply=True, write_timeout=60
            )

        if reply_text is not None:
            await reply_text.delete()

        logger.info("用户 %s[%s] [bold]深渊挑战数据[/bold]: 成功发送图片", user.full_name, user.id, extra={"markup": True})

    async def get_rendered_pic(
        self, client: Client, uid: int, floor: int, total: bool, previous: bool
    ) -> Union[
        Tuple[
            Union[BaseException, Any],
            Union[BaseException, Any],
            Union[BaseException, Any],
            Union[BaseException, Any],
            Union[BaseException, Any],
        ],
        List[RenderResult],
        None,
    ]:
        """
        获取渲染后的图片

        Args:
            client (Client): 获取 genshin 数据的 client
            uid (int): 需要查询的 uid
            floor (int): 层数
            total (bool): 是否为总览
            previous (bool): 是否为上期

        Returns:
            bytes格式的图片
        """

        def json_encoder(value):
            if isinstance(value, datetime):
                return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S")
            return value

        abyss_data = await client.get_spiral_abyss(uid, previous=previous, lang="zh-cn")

        if not abyss_data.unlocked:
            raise AbyssUnlocked()
        if not abyss_data.ranks.most_kills:
            raise NoMostKills()
        if (total or (floor > 0)) and not abyss_data.floors[0].chambers[0].battles:
            raise AbyssNotFoundError

        start_time = abyss_data.start_time.astimezone(TZ)
        time = start_time.strftime("%Y年%m月") + ("上" if start_time.day <= 15 else "下")
        stars = [i.stars for i in filter(lambda x: x.floor > 8, abyss_data.floors)]
        total_stars = f"{sum(stars)} ({'-'.join(map(str, stars))})"

        render_data = {}
        result = await async_re_sub(
            regex_01, partial(replace_01, assets_service=self.assets_service), abyss_data.json(encoder=json_encoder)
        )
        result = await async_re_sub(regex_02, partial(replace_02, assets_service=self.assets_service), result)

        render_data["time"] = time
        render_data["stars"] = total_stars
        render_data["uid"] = uid
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
            avatars = await client.get_genshin_characters(uid, lang="zh-cn")
            render_data["avatar_data"] = {i.id: i.constellation for i in avatars}
            data = jsonlib.loads(result)
            render_data["data"] = data

            render_inputs: List[Tuple[int, Coroutine[Any, Any, RenderResult]]] = []

            def overview_task():
                return -1, self.template_service.render(
                    "genshin/abyss/overview.html", render_data, viewport={"width": 750, "height": 580}
                )

            def floor_task(floor_index: int):
                floor_d = data["floors"][floor_index]
                return (
                    floor_d["floor"],
                    self.template_service.render(
                        "genshin/abyss/floor.html",
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
                    "genshin/abyss/overview.html", render_data, viewport={"width": 750, "height": 580}
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
        if (floor_data := list(filter(lambda x: x["floor"] == floor, floors))) is None:
            return None
        avatars = await client.get_genshin_characters(uid, lang="zh-cn")
        render_data["avatar_data"] = {i.id: i.constellation for i in avatars}
        render_data["floor"] = floor_data[0]
        render_data["total_stars"] = f"{floor_data[0]['stars']}/{floor_data[0]['max_stars']}"
        return [
            await self.template_service.render(
                "genshin/abyss/floor.html", render_data, viewport={"width": 690, "height": 500}
            )
        ]
