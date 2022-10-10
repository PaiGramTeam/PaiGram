from typing import Dict, Optional

from genshin import Client
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError, TooManyRequestPublicCookies
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user import UserService
from core.user.error import UserNotFoundError
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client, get_public_genshin_client
from utils.log import logger


class AbyssUnlocked(Exception):
    """根本没动"""

    pass


class NoMostKills(Exception):
    """挑战了但是数据没刷新"""

    pass


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

    @staticmethod
    def _get_role_star_bg(value: int):
        if value == 4:
            return "./background/roleStarBg4.png"
        elif value == 5:
            return "./background/roleStarBg5.png"
        else:
            raise ValueError("错误的数据")

    async def _get_abyss_data(self, client: Client, uid: Optional[int] = None) -> Dict:
        if uid is None:
            _uid = client.uid
            await client.get_record_cards()
        else:
            _uid = uid
        spiral_abyss_info = await client.get_spiral_abyss(_uid)
        if not spiral_abyss_info.unlocked:
            raise AbyssUnlocked
        ranks = spiral_abyss_info.ranks
        if len(spiral_abyss_info.ranks.most_kills) == 0:
            raise NoMostKills
        abyss_data = {
            "uid": _uid,
            "max_floor": spiral_abyss_info.max_floor,
            "total_battles": spiral_abyss_info.total_battles,
            "total_stars": spiral_abyss_info.total_stars,
            "most_played_list": [],
            "most_kills": {
                "icon": await self.assets_service.avatar(ranks.most_kills[0].id).side(),
                "value": ranks.most_kills[0].value,
            },
            "strongest_strike": {
                "icon": await self.assets_service.avatar(ranks.strongest_strike[0].id).side(),
                "value": ranks.strongest_strike[0].value,
            },
            "most_damage_taken": {
                "icon": await self.assets_service.avatar(ranks.most_damage_taken[0].id).side(),
                "value": ranks.most_damage_taken[0].value,
            },
            "most_bursts_used": {
                "icon": await self.assets_service.avatar(ranks.most_bursts_used[0].id).side(),
                "value": ranks.most_bursts_used[0].value,
            },
            "most_skills_used": {
                "icon": await self.assets_service.avatar(ranks.most_skills_used[0].id).side(),
                "value": ranks.most_skills_used[0].value,
            },
        }
        # most_kills
        most_played_list = ranks.most_played
        for most_played in most_played_list:
            temp = {
                "icon": await self.assets_service.avatar(most_played.id).icon(),
                "value": most_played.value,
                "background": self._get_role_star_bg(most_played.rarity),
            }
            abyss_data["most_played_list"].append(temp)
        return abyss_data

    @handler(CommandHandler, command="abyss", block=False)
    @handler(MessageHandler, filters=filters.Regex("^深渊数据查询(.*)"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 查深渊挑战命令请求")
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            try:
                client = await get_genshin_client(user.id)
                abyss_data = await self._get_abyss_data(client)
            except CookiesNotFoundError:
                client, uid = await get_public_genshin_client(user.id)
                abyss_data = await self._get_abyss_data(client, uid)
        except UserNotFoundError:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 10)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
            return
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多 请稍后重试")
            return
        except (AbyssUnlocked, NoMostKills):
            await message.reply_text("本次深渊旅行者还没挑战呢，咕咕咕~~~")
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        png_data = await self.template_service.render(
            "genshin/abyss", "abyss.html", abyss_data, {"width": 865, "height": 504}, full_page=False
        )
        await message.reply_photo(png_data, filename=f"abyss_{user.id}.png", allow_sending_without_reply=True)
