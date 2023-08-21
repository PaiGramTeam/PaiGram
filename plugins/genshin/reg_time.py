from datetime import datetime
from typing import TYPE_CHECKING

from simnet.client.routes import InternationalRoute
from simnet.errors import BadRequest as SIMNetBadRequest
from simnet.utils.player import recognize_genshin_server, recognize_genshin_game_biz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import filters
from telegram.helpers import create_deep_linked_url

from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.users.services import UserService
from plugins.tools.genshin import PlayerNotFoundError, CookiesNotFoundError, GenshinHelper
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from simnet import GenshinClient

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

REG_TIME_URL = InternationalRoute(
    overseas="https://sg-hk4e-api.hoyoverse.com/event/e20220928anniversary/game_data",
    chinese="https://hk4e-api.mihoyo.com/event/e20220928anniversary/game_data",
)


class RegTimePlugin(Plugin):
    """查询原神注册时间"""

    def __init__(
        self,
        user_service: UserService = None,
        cookie_service: CookiesService = None,
        helper: GenshinHelper = None,
        redis: RedisDB = None,
    ):
        self.cache = redis.client
        self.cache_key = "plugin:reg_time:"
        self.user_service = user_service
        self.cookie_service = cookie_service
        self.helper = helper

    @staticmethod
    async def get_reg_time(client: "GenshinClient") -> str:
        """获取原神注册时间"""
        game_biz = recognize_genshin_game_biz(client.player_id)
        region = recognize_genshin_server(client.player_id)
        await client.get_hk4e_token_by_cookie_token(game_biz, region)
        url = REG_TIME_URL.get_url(client.region)
        params = {"game_biz": game_biz, "lang": "zh-cn", "badge_uid": client.player_id, "badge_region": region}
        data = await client.request_lab(url, method="GET", params=params)
        if time := jsonlib.loads(data.get("data", "{}")).get("1", 0):
            return datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S")
        raise RegTimePlugin.NotFoundRegTimeError

    async def get_reg_time_from_cache(self, client: "GenshinClient") -> str:
        """从缓存中获取原神注册时间"""
        if reg_time := await self.cache.get(f"{self.cache_key}{client.player_id}"):
            return reg_time.decode("utf-8")
        reg_time = await self.get_reg_time(client)
        await self.cache.set(f"{self.cache_key}{client.player_id}", reg_time)
        return reg_time

    @handler.command("reg_time", block=False)
    @handler.message(filters.Regex(r"^原神账号注册时间$"), block=False)
    async def reg_time(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 原神注册时间命令请求", user.full_name, user.id)
        try:
            async with self.helper.genshin(user.id) as client:
                game_uid = client.player_id
                reg_time = await self.get_reg_time_from_cache(client)
            await message.reply_text(f"你的原神账号 [{game_uid}] 注册时间为：{reg_time}")
        except (PlayerNotFoundError, CookiesNotFoundError):
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_msg = await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙绑定账号",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML,
                )
                self.add_delete_message_job(reply_msg, delay=30)
                self.add_delete_message_job(message, delay=30)
            else:
                await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙进行绑定",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        except SIMNetBadRequest as exc:
            if exc.ret_code == -501101:
                await message.reply_text("当前角色冒险等阶未达到10级，暂时无法获取信息")
            else:
                raise exc
        except RegTimePlugin.NotFoundRegTimeError:
            await message.reply_text("未找到你的原神账号 [{game_uid}] 注册时间，仅限 2022 年 10 月 之前注册的账号")

    class NotFoundRegTimeError(Exception):
        """未找到注册时间"""
