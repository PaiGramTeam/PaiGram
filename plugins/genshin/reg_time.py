from datetime import datetime


from genshin import Client, GenshinException
from genshin.client.routes import InternationalRoute  # noqa F401
from genshin.utility import recognize_genshin_server, get_ds_headers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext, MessageHandler
from telegram.ext import filters
from telegram.helpers import create_deep_linked_url

from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.user import UserService
from core.user.error import UserNotFoundError
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.genshin import fetch_hk4e_token_by_cookie, recognize_genshin_game_biz
from utils.helpers import get_genshin_client
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

REG_TIME_URL = InternationalRoute(
    overseas="https://sg-hk4e-api.hoyoverse.com/event/e20220928anniversary/game_data",
    chinese="https://hk4e-api.mihoyo.com/event/e20220928anniversary/game_data",
)


class RegTimePlugin(Plugin, BasePlugin):
    """查询原神注册时间"""

    def __init__(
        self,
        user_service: UserService = None,
        cookie_service: CookiesService = None,
        redis: RedisDB = None,
    ):
        self.cache = redis.client
        self.cache_key = "plugin:reg_time:"
        self.user_service = user_service
        self.cookie_service = cookie_service

    @staticmethod
    async def get_reg_time(client: Client) -> str:
        """获取原神注册时间"""
        await fetch_hk4e_token_by_cookie(client)
        url = REG_TIME_URL.get_url(client.region)
        params = {
            "game_biz": recognize_genshin_game_biz(client.uid),
            "lang": "zh-cn",
            "badge_uid": client.uid,
            "badge_region": recognize_genshin_server(client.uid),
        }
        headers = get_ds_headers(
            client.region,
            params=params,
            lang="zh-cn",
        )
        data = await client.cookie_manager.request(url, method="GET", params=params, headers=headers)
        if time := jsonlib.loads(data.get("data", "{}")).get("1", 0):
            return datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S")
        raise RegTimePlugin.NotFoundRegTimeError

    async def get_reg_time_from_cache(self, client: Client) -> str:
        """从缓存中获取原神注册时间"""
        if reg_time := await self.cache.get(f"{self.cache_key}{client.uid}"):
            return reg_time.decode("utf-8")
        reg_time = await self.get_reg_time(client)
        await self.cache.set(f"{self.cache_key}{client.uid}", reg_time)
        return reg_time

    @handler(CommandHandler, command="reg_time", block=False)
    @handler(MessageHandler, filters=filters.Regex("^原神账号注册时间$"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 原神注册时间命令请求", user.full_name, user.id)
        try:
            client = await get_genshin_client(user.id)
            game_uid = client.uid
            reg_time = await self.get_reg_time_from_cache(client)
            await message.reply_text(f"你的原神账号 [{game_uid}] 注册时间为：{reg_time}")
        except (UserNotFoundError, CookiesNotFoundError):
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_msg = await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙绑定账号",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML,
                )
                self._add_delete_message_job(context, reply_msg.chat_id, reply_msg.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙进行绑定",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        except GenshinException as exc:
            if exc.retcode == -501101:
                await message.reply_text("当前角色冒险等阶未达到10级，暂时无法获取信息")
            else:
                raise exc
        except RegTimePlugin.NotFoundRegTimeError:
            await message.reply_text("未找到你的原神账号 [{game_uid}] 注册时间，仅限 2022 年 10 月 之前注册的账号")

    class NotFoundRegTimeError(Exception):
        """未找到注册时间"""
