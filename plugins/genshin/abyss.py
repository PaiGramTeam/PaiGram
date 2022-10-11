"""深渊数据查询"""
import re
from functools import partial
from typing import Match, Tuple

import ujson as json
from genshin import Client
from pytz import timezone
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user import UserService
from core.user.error import UserNotFoundError
from metadata.genshin import game_id_to_role_id
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import async_re_sub, get_genshin_client, get_public_genshin_client
from utils.log import logger

TZ = timezone("Asia/Shanghai")
cmd_pattern = r"^/abyss\s*((?:\d+)|(?:all))?\s*(pre)?"
msg_pattern = r"^深渊数据((?:查询)|(?:总览))(上期){0,1}\D*(\d+)?.*$"

regex_01 = r"['\"]icon['\"]:\s*['\"](.*?)['\"]"
regex_02 = r"['\"]side_icon['\"]:\s*['\"](.*?)['\"]"


async def replace_01(match: Match, assets_service: AssetsService) -> str:
    aid = game_id_to_role_id(re.findall(r"UI_AvatarIcon_(.*?).png", match.group(1))[0])
    return (await assets_service.avatar(aid).icon()).as_uri()


async def replace_02(match: Match, assets_service: AssetsService) -> str:
    aid = game_id_to_role_id(re.findall(r"UI_AvatarIcon_Side_(.*?).png", match.group(1))[0])
    return (await assets_service.avatar(aid).side()).as_uri()


def get_args(text: str) -> Tuple[int, bool, bool]:
    if text.startswith("/"):
        result = re.match(cmd_pattern, text).groups()
        try:
            floor = int(result[0] or 0)
        except ValueError:
            floor = 0
        return floor, result[0] == "all", bool(result[1])
    else:
        result = re.match(msg_pattern, text).groups()
        return int(result[2] or 0), result[0] == "查询", result[1] == "上期"


class AbyssUnlocked(Exception):
    """根本没动"""


class NoMostKills(Exception):
    """挑战了但是数据没刷新"""


class Abyss(Plugin, BasePlugin):
    """深渊数据查询"""

    def __init__(
        self,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
        template_service: TemplateService = None,
        assets_service: AssetsService = None,
    ):
        self.template_service = template_service
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.assets_service = assets_service

    @handler.command("abyss", block=False)
    @handler.message(filters.Regex(msg_pattern), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message

        # 若查询帮助
        if (message.text.startswith("/") and "help" in message.text) or "帮助" in message.text:
            await message.reply_text(
                "<b>深渊挑战数据</b>功能使用帮助（中括号表示可选参数）\n\n"
                "指令格式：\n<code>/abyss + [层数/all] + [pre]</code>\n（<pre>pre</pre>表示上期）\n\n"
                "文本格式：\n<code>深渊数据 + 查询/总览 + [上期] + [层数]</code> \n\n"
                "例如以下指令都正确：\n"
                "<code>/abyss</code>\n<code>/abyss 12 pre</code>\n<code>/abyss all code</code>\n"
                "<code>深渊数据查询</code>\n<code>深渊数据查询上期第12层</code>\n<code>深渊数据总览上期</code>",
                parse_mode=ParseMode.HTML,
            )
            logger.info(f"用户 {user.full_name}[{user.id}] 查询[bold]深渊挑战数据[/bold]帮助", extra={"markup": True})
            return

        # 解析参数
        floor, total, previous = get_args(message.text)

        logger.info(
            f"用户 {user.full_name}[{user.id}] [bold]深渊挑战数据[/bold]请求: "
            f"floor={floor} overview={total} previous={previous}",
            extra={"markup": True},
        )

        try:
            client = await get_genshin_client(user.id)
            await client.get_record_cards()
            uid = client.uid
        except UserNotFoundError:  # 若未找到账号
            reply_msg = await message.reply_text(
                "未查询到账号信息，请先私聊<a href='https://t.me/PaimonMasterBot'>派蒙</a>", parse_mode=ParseMode.HTML
            )
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_msg.chat_id, reply_msg.message_id, 10)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
            return
        except CookiesNotFoundError:  # 若未找到cookie
            client, uid = await get_public_genshin_client(user.id)

        await message.reply_chat_action(ChatAction.TYPING)

        try:
            image = await self.get_rendered_pic(client, uid, floor, total, previous)
        except AbyssUnlocked:  # 若深渊未解锁
            user = await client.get_genshin_user(uid)
            reply_msg = await message.reply_text(
                f"旅行者 <pre>{user.info.nickname}({uid})</pre> 还未解锁深渊哦~", parse_mode=ParseMode.HTML
            )
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_msg.chat_id, reply_msg.message_id, 10)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
            return
        except NoMostKills:  # 若深渊还未挑战
            user = await client.get_genshin_user(uid)
            reply_msg = await message.reply_text(
                f"本次深渊旅行者 <pre>{user.info.nickname}({uid})</pre> 还没有挑战呢，咕咕咕~", parse_mode=ParseMode.HTML
            )
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_msg.chat_id, reply_msg.message_id, 10)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
            return

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        await message.reply_photo(image, filename=f"abyss_{user.id}.png", allow_sending_without_reply=True)

    async def get_rendered_pic(self, client: Client, uid: int, floor: int, total: bool, previous: bool) -> bytes:

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

        abyss_data = await client.get_spiral_abyss(uid, previous=previous)
        if not abyss_data.unlocked:
            raise AbyssUnlocked()
        if not abyss_data.ranks.most_kills:
            raise NoMostKills()
        end_time = abyss_data.end_time.replace(tzinfo=TZ)
        time = end_time.strftime("%Y年%m月") + "上" if end_time.day <= 15 else "下" + "期"
        stars = [i.stars for i in filter(lambda x: x.floor > 8, abyss_data.floors)]
        total_stars = f"{sum(stars)} ({'-'.join(map(str, stars))})"

        render_data = {}
        result = await async_re_sub(
            regex_01, partial(replace_01, assets_service=self.assets_service), abyss_data.json()
        )
        result = await async_re_sub(regex_02, partial(replace_02, assets_service=self.assets_service), result)

        render_data["data"] = json.loads(result)
        render_data["time"] = time
        render_data["stars"] = total_stars
        render_data["uid"] = uid
        if total:
            return await self.template_service.render(
                "genshin/abyss",
                "overview.html",
                render_data,
                viewport={"width": 770, "height": 600},
                omit_background=True,
            )
        elif floor < 1:
            return await self.template_service.render(
                "genshin/abyss",
                "overview.html",
                render_data,
                viewport={"width": 750, "height": 580},
                omit_background=True,
            )
        elif floor > 0:
            render_data["floor"] = floor
            return await self.template_service.render("genshin/abyss", "floor.html", render_data)
        return await self.template_service.render("genshin/abyss", "total.html", render_data)
