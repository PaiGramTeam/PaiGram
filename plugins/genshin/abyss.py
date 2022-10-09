"""深渊数据查询"""
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

from genshin import Client
from genshin.models import CharacterRanks
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
from modules.wiki.base import Model
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client, get_public_genshin_client
from utils.log import logger
from utils.typedefs import StrOrInt

TZ = timezone("Asia/Shanghai")
cmd_pattern = r"^/abyss\s*(?:(\d+)|(all))?\s*(pre)?"
msg_pattern = r"^深渊数据((?:查询)|(?:总览))(上期){0,1}\D*(\d+)?.*$"


def get_args(text: str) -> Tuple[int, bool, bool]:
    if text.startswith("/"):
        result = re.match(cmd_pattern, text).groups()
        return int(result[0] or 0), bool(result[1]), bool(result[2])
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
        floor, overview, previous = get_args(message.text)

        logger.info(
            f"用户 {user.full_name}[{user.id}] [bold]深渊挑战数据[/bold]请求: "
            f"floor={floor} overview={overview} previous={previous}",
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
            image = await self.get_rendered_pic(client, uid, floor, overview, previous)
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

    async def get_rendered_pic(self, client: Client, uid: int, floor: int, overview: bool, previous: bool) -> bytes:
        """
        获取渲染后的图片

        Args:
            client (Client): 获取 genshin 数据的 client
            uid (int): 需要查询的 uid
            floor (int): 层数
            overview (bool): 是否为总览
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
        render_data = {}
        if overview:
            most_played: List[Avatar] = []
            ranks: CharacterRanks = abyss_data.ranks
            for avatar in ranks.most_played:
                most_played.append(Avatar(img=await self.assets_service.avatar(avatar.id).icon(), value=avatar.value))
            most_kills = Avatar(
                img=await self.assets_service.avatar(ranks.most_kills[0].id).side(), value=ranks.most_kills[0].value
            )
            strongest_strike = Avatar(
                img=await self.assets_service.avatar(ranks.strongest_strike[0].id).side(),
                value=ranks.strongest_strike[0].value,
            )
            most_damage_taken = Avatar(
                img=await self.assets_service.avatar(ranks.most_damage_taken[0].id).side(),
                value=ranks.most_damage_taken[0].value,
            )
            most_bursts_used = Avatar(
                img=await self.assets_service.avatar(ranks.most_bursts_used[0].id).side(),
                value=ranks.most_bursts_used[0].value,
            )
            most_skills_used = Avatar(
                img=await self.assets_service.avatar(ranks.most_skills_used[0].id).side(),
                value=ranks.most_skills_used[0].value,
            )
            total = Total(
                time=time,
                season=abyss_data.season,
                stars=abyss_data.total_stars,
                deep=abyss_data.max_floor,
                battles=abyss_data.total_battles,
                most_played=most_played,
                most_kills=most_kills,
                strongest_strike=strongest_strike,
                most_damage_taken=most_damage_taken,
                most_bursts_used=most_bursts_used,
                most_skills_used=most_skills_used,
            )
            floors: List[Floor] = []
            for floor in abyss_data.floors:
                rooms: List[Room] = []
                for room in floor.chambers:
                    time = room.battles[0].timestamp.replace(tzinfo=TZ)
                    stars = room.stars
                    avatar_lists = []
                    for battle in room.battles:
                        avatars = []
                        for avatar in battle.characters:
                            avatars.append(
                                Avatar(
                                    img=await self.assets_service.avatar(avatar.id).icon(),
                                    value=avatar.level or avatar.name,
                                    extra={"element": avatar.element},
                                )
                            )
                        avatar_lists.append(avatars)
                    rooms.append(Room(time=time, stars=stars, avatar_lists=avatar_lists))
                floors.append(Floor(num=floor.floor, rooms=rooms))
            return await self.template_service.render(
                "genshin/abyss", "overview.html", {"data": Overview(total=total, floors=floors)}
            )
        elif floor < 1:
            return await self.template_service.render("genshin/abyss", "total.html", render_data)
        else:
            return await self.template_service.render("genshin/abyss", "abyss.html", render_data)


class Avatar(Model):
    img: Path
    value: StrOrInt
    extra: dict = {}


class Room(Model):
    time: datetime
    stars: int
    avatar_lists: Iterable[Iterable[Avatar]]


class Floor(Model):
    num: int
    rooms: Iterable[Room]


class Total(Model):
    time: str
    season: int
    stars: int
    deep: str
    battles: int
    most_played: Iterable[Avatar]

    most_kills: Avatar
    """最多击破"""

    strongest_strike: Avatar
    """最强一击"""

    most_damage_taken: Avatar
    """最多承伤"""

    most_bursts_used: Avatar
    """最多Q"""

    most_skills_used: Avatar
    """最多E"""


class Overview(Model):
    total: Total
    floors: Iterable[Floor]
