import random
from typing import Optional

from genshin import Client
from genshin.models import GenshinUserStats
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.helpers import create_deep_linked_url

from core.baseplugin import BasePlugin
from core.services.cookies import CookiesNotFoundError, TooManyRequestPublicCookies
from core.plugin import Plugin, handler
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from core.services.user import UserNotFoundError
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file, get_genshin_client, get_public_genshin_client
from utils.log import logger


class UserStatsPlugins(Plugin, BasePlugin):
    """玩家统计查询"""

    def __init__(self, template_service: TemplateService = None):
        self.template_service = template_service

    @handler(CommandHandler, command="stats", block=False)
    @handler(MessageHandler, filters=filters.Regex("^玩家统计查询(.*)"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> Optional[int]:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 查询游戏用户命令请求")
        uid: Optional[int] = None
        try:
            args = context.args
            if args is not None and len(args) >= 1:
                uid = int(args[0])
        except ValueError as exc:
            logger.warning(f"获取 uid 发生错误！ 错误信息为 {repr(exc)}")
            await message.reply_text("输入错误")
            return
        try:
            try:
                client = await get_genshin_client(user.id)
            except CookiesNotFoundError:
                client, uid = await get_public_genshin_client(user.id)
            render_result = await self.render(client, uid)
        except UserNotFoundError:
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_uid"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
            return
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多 请稍后重试")
            return
        except AttributeError as exc:
            logger.error("角色数据有误")
            logger.exception(exc)
            await message.reply_text("角色数据有误 估计是派蒙晕了")
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename=f"{client.uid}.png", allow_sending_without_reply=True)

    async def render(self, client: Client, uid: Optional[int] = None) -> RenderResult:
        if uid is None:
            uid = client.uid

        user_info = await client.get_genshin_user(uid)
        logger.debug(user_info)

        # 因为需要替换线上图片地址为本地地址，先克隆数据，避免修改原数据
        user_info = user_info.copy(deep=True)

        data = {
            "uid": uid,
            "info": user_info.info,
            "stats": user_info.stats,
            "explorations": user_info.explorations,
            "teapot": user_info.teapot,
            "stats_labels": [
                ("活跃天数", "days_active"),
                ("成就达成数", "achievements"),
                ("获取角色数", "characters"),
                ("深境螺旋", "spiral_abyss"),
                ("解锁传送点", "unlocked_waypoints"),
                ("解锁秘境", "unlocked_domains"),
                ("奇馈宝箱数", "remarkable_chests"),
                ("华丽宝箱数", "luxurious_chests"),
                ("珍贵宝箱数", "precious_chests"),
                ("精致宝箱数", "exquisite_chests"),
                ("普通宝箱数", "common_chests"),
                ("风神瞳", "anemoculi"),
                ("岩神瞳", "geoculi"),
                ("雷神瞳", "electroculi"),
                ("草神瞳", "dendroculi"),
            ],
            "style": random.choice(["mondstadt", "liyue"]),  # nosec
        }

        # html = await self.template_service.render_async(
        #     "genshin/stats/stats.html", data
        # )
        # logger.debug(html)

        await self.cache_images(user_info)

        return await self.template_service.render(
            "genshin/stats/stats.html",
            data,
            {"width": 650, "height": 800},
            full_page=True,
        )

    @staticmethod
    async def cache_images(data: GenshinUserStats) -> None:
        """缓存所有图片到本地"""
        # TODO: 并发下载所有资源

        # 探索地区
        for item in data.explorations:
            item.__config__.allow_mutation = True
            item.icon = await url_to_file(item.icon)
            item.cover = await url_to_file(item.cover)
