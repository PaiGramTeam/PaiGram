from datetime import datetime
from typing import TYPE_CHECKING

from simnet.client.routes import InternationalRoute
from simnet.errors import BadRequest as SIMNetBadRequest
from simnet.utils.player import recognize_genshin_server, recognize_genshin_game_biz
from telegram.ext import filters

from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.users.services import UserService
from plugins.tools.genshin import GenshinHelper
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


class NotFoundRegTimeError(Exception):
    """未找到注册时间"""


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
        raise NotFoundRegTimeError

    async def get_reg_time_from_cache(self, client: "GenshinClient") -> str:
        """从缓存中获取原神注册时间"""
        if reg_time := await self.cache.get(f"{self.cache_key}{client.player_id}"):
            return reg_time.decode("utf-8")
        reg_time = await self.get_reg_time(client)
        await self.cache.set(f"{self.cache_key}{client.player_id}", reg_time)
        return reg_time

    @handler.command("reg_time", block=False)
    @handler.message(filters.Regex(r"^原神账号注册时间$"), block=False)
    async def reg_time(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        self.log_user(update, logger.info, "原神注册时间命令请求")
        try:
            async with self.helper.genshin(user_id) as client:
                reg_time = await self.get_reg_time_from_cache(client)
            await message.reply_text(f"你的原神账号注册时间为：{reg_time}")
        except SIMNetBadRequest as exc:
            if exc.ret_code == -501101:
                await message.reply_text("当前角色冒险等阶未达到10级，暂时无法获取信息")
            else:
                raise exc
        except ValueError as exc:
            if "cookie_token" in str(exc):
                await message.reply_text("呜呜呜出错了请重新绑定账号")
            else:
                raise exc
        except NotFoundRegTimeError:
            await message.reply_text("未找到你的原神账号注册时间，仅限 2022 年 10 月 之前注册的账号")
