from http.cookies import SimpleCookie
from typing import List, TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel
from telegram import (
    InlineKeyboardButton,
    SwitchInlineQueryChosenChat,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineQueryResultsButton,
)
from telegram.ext import filters
from telegram.error import BadRequest
from telegram.helpers import create_deep_linked_url

from gram_core.basemodel import RegionEnum
from gram_core.config import config
from gram_core.dependence.redisdb import RedisDB
from gram_core.plugin import Plugin, handler
from gram_core.services.cookies import CookiesService
from gram_core.services.devices import DevicesService
from utils.log import logger

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

if TYPE_CHECKING:
    from telegram import Update, InlineQuery
    from telegram.ext import ContextTypes


class InlineCookies(BaseModel):
    account_id: int
    region: RegionEnum
    data: str


class CookiesExport(Plugin):
    def __init__(
        self,
        redis: RedisDB,
        cookies_service: CookiesService,
        devices_service: DevicesService,
    ):
        self.qname = "plugin:cookies_export:"
        self.ex = 5 * 60
        self.client = redis.client
        self.cookies_service = cookies_service
        self.devices_service = devices_service

    def get_cache_key(self, user_id: int) -> str:
        return f"{self.qname}{user_id}"

    async def set_cache(self, user_id: int, data: List[InlineCookies]) -> None:
        if not data:
            return
        new_data = jsonlib.dumps([i.dict() for i in data])
        await self.client.set(self.get_cache_key(user_id), new_data, ex=self.ex)

    async def get_cache(self, user_id: int) -> List[InlineCookies]:
        _data = await self.client.get(self.get_cache_key(user_id))
        if _data is None:
            return []
        data_str = _data.decode("utf-8")
        data = jsonlib.loads(data_str)
        return [InlineCookies(**i) for i in data]

    async def get_all_cookies(self, user_id: int) -> List[InlineCookies]:
        cookies = await self.cookies_service.get_all(user_id)
        if not cookies:
            return []
        cookies_list = []
        for cookie in cookies:
            if cookie.region not in [RegionEnum.HYPERION, RegionEnum.HOYOLAB]:
                continue
            cookies = SimpleCookie()
            for key, value in cookie.data.items():
                cookies[key] = value

            device = None
            if cookie.region == RegionEnum.HYPERION:
                device = await self.devices_service.get(cookie.account_id)
            if device is not None:
                cookies["x-rpc-device_id"] = device.device_id
                cookies["x-rpc-device_fp"] = device.device_fp
            cookie_str = cookies.output(header="", sep=";")

            cookies_list.append(
                InlineCookies(
                    account_id=cookie.account_id,
                    region=cookie.region,
                    data=cookie_str,
                )
            )
        await self.set_cache(user_id, cookies_list)
        return cookies_list

    @handler.command("cookies_export", block=False)
    @handler.command("start", filters=filters.Regex("cookies_export$"), block=False)
    async def cookies_export(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] cookies_export 命令请求", message.from_user.full_name, message.from_user.id)
        data = await self.get_all_cookies(user.id)
        if not data:
            await message.reply_text("没有查询到任何账号信息")
            return
        text = "请点击下方按钮导出账号信息到指定 BOT"
        buttons = [
            [
                InlineKeyboardButton(
                    "选择需要导入账号的 BOT",
                    switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
                        query="cookies_export", allow_bot_chats=True
                    ),
                )
            ]
        ]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    def gen_cookies_import_buttons(self):
        official_bots = config.bot_official.copy()
        lower_official_bots = [i.lower() for i in official_bots]
        bot_username_lower = self.application.bot.username.lower()
        if bot_username_lower in lower_official_bots:
            official_bots.pop(lower_official_bots.index(bot_username_lower))
        return [
            [
                InlineKeyboardButton(
                    text=name,
                    url=create_deep_linked_url(name, "cookies_export"),
                )
            ]
            for name in official_bots
        ]

    @handler.command("cookies_import", block=False)
    @handler.command("start", filters=filters.Regex("cookies_import$"), block=False)
    async def cookies_import(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] cookies_import 命令请求", user.full_name, user.id)
        text = "请点击下方按钮选择您已经绑定了账号的 BOT"
        buttons = self.gen_cookies_import_buttons()
        if not buttons:
            await message.reply_text("没有可用的BOT")
            return
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    @handler.inline_query(pattern="^cookies_export$", block=False)
    async def inline_query(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        user = update.effective_user
        ilq: "InlineQuery" = update.inline_query
        cache_data = await self.get_cache(user.id)
        results_list = []
        if not cache_data:
            results_list.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="无法导出 Cookies",
                    description="请先使用命令 /cookies_export",
                    input_message_content=InputTextMessageContent("/cookies_export"),
                )
            )
        else:
            name_map = {RegionEnum.HYPERION: "米游社", RegionEnum.HOYOLAB: "HoYoLab"}
            for cookie in cache_data:
                region = name_map[cookie.region]
                results_list.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title=f"{region} - {cookie.account_id}",
                        description=f"导出账号ID {cookie.account_id} 的 Cookies",
                        input_message_content=InputTextMessageContent(f"/setcookies {region} {cookie.data}"),
                    )
                )
        try:
            await ilq.answer(
                results=results_list,
                cache_time=0,
                auto_pagination=True,
                button=InlineQueryResultsButton(
                    text="！！导出到不信任对话将有盗号风险！!",
                    start_parameter="cookies_export",
                ),
            )
        except BadRequest as exc:
            if "Query is too old" in exc.message:  # 过时请求全部忽略
                logger.warning("用户 %s[%s] inline_query 请求过时", user.full_name, user.id)
                return
            if "can't parse entities" not in exc.message:
                raise exc
            logger.warning("inline_query发生BadRequest错误", exc_info=exc)
            await ilq.answer(
                results=[],
                button=InlineQueryResultsButton(
                    text="糟糕，发生错误了。",
                    start_parameter="inline_message",
                ),
            )
