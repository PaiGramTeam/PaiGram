import re
from datetime import datetime
from typing import List, Optional

from genshin import Client, GenshinException
from genshin.client.routes import Route
from genshin.utility import recognize_genshin_server
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import filters, MessageHandler, CommandHandler, CallbackContext
from telegram.helpers import create_deep_linked_url

from core.basemodel import RegionEnum
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.users.services import UserService
from metadata.genshin import AVATAR_DATA
from metadata.shortname import roleToId, roleToName
from modules.apihelper.client.components.calendar import Calendar
from plugins.tools.genshin import GenshinHelper, CookiesNotFoundError, PlayerNotFoundError
from utils.genshin import fetch_hk4e_token_by_cookie, recognize_genshin_game_biz
from utils.log import logger

BIRTHDAY_URL = Route(
    "https://hk4e-api.mihoyo.com/event/birthdaystar/account/post_my_draw",
)


def rm_starting_str(string, starting):
    """Remove the starting character from a string."""
    while string[0] == str(starting):
        string = string[1:]
    return string


class BirthdayPlugin(Plugin):
    """Birthday."""

    def __init__(
        self,
        user_service: UserService,
        helper: GenshinHelper,
        cookie_service: CookiesService,
    ):
        """Load Data."""
        self.birthday_list = {}
        self.user_service = user_service
        self.cookie_service = cookie_service
        self.helper = helper

    async def initialize(self):
        self.birthday_list = await Calendar.async_gen_birthday_list()
        self.birthday_list.get("6_1", []).append("派蒙")

    async def get_today_birthday(self) -> List[str]:
        key = (
            rm_starting_str(datetime.now().strftime("%m"), "0")
            + "_"
            + rm_starting_str(datetime.now().strftime("%d"), "0")
        )
        return (self.birthday_list.get(key, [])).copy()

    @handler.command(command="birthday", block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        key = (
            rm_starting_str(datetime.now().strftime("%m"), "0")
            + "_"
            + rm_starting_str(datetime.now().strftime("%d"), "0")
        )
        args = self.get_args(context)

        if len(args) >= 1:
            msg = args[0]
            logger.info("用户 %s[%s] 查询角色生日命令请求 || 参数 %s", user.full_name, user.id, msg)
            if re.match(r"\d{1,2}.\d{1,2}", msg):
                try:
                    month = rm_starting_str(re.findall(r"\d+", msg)[0], "0")
                    day = rm_starting_str(re.findall(r"\d+", msg)[1], "0")
                    key = f"{month}_{day}"
                    day_list = self.birthday_list.get(key, [])
                    date = f"{month}月{day}日"
                    text = f"{date} 是 {'、'.join(day_list)} 的生日哦~" if day_list else f"{date} 没有角色过生日哦~"
                except IndexError:
                    text = "请输入正确的日期格式，如1-1，或输入正确的角色名称。"
                reply_message = await message.reply_text(text)

            else:
                try:
                    if msg == "派蒙":
                        text = "派蒙的生日是6月1日哦~"
                    elif roleToName(msg) == "旅行者":
                        text = "喂，旅行者！你该不会忘掉自己的生日了吧？"
                    else:
                        name = roleToName(msg)
                        aid = str(roleToId(msg))
                        birthday = AVATAR_DATA[aid]["birthday"]
                        text = f"{name} 的生日是 {birthday[0]}月{birthday[1]}日 哦~"
                    reply_message = await message.reply_text(text)

                except KeyError:
                    reply_message = await message.reply_text("请输入正确的日期格式，如1-1，或输入正确的角色名称。")

        else:
            logger.info("用户 %s[%s] 查询今日角色生日列表", user.full_name, user.id)
            today_list = await self.get_today_birthday()
            text = f"今天是 {'、'.join(today_list)} 的生日哦~" if today_list else "今天没有角色过生日哦~"
            reply_message = await message.reply_text(text)

        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(message)
            self.add_delete_message_job(reply_message)

    @staticmethod
    async def get_card(client: Client, role_id: int) -> None:
        """领取画片"""
        url = BIRTHDAY_URL.get_url()
        params = {
            "game_biz": recognize_genshin_game_biz(client.uid),
            "lang": "zh-cn",
            "badge_uid": client.uid,
            "badge_region": recognize_genshin_server(client.uid),
            "activity_id": "20220301153521",
        }
        json = {
            "role_id": role_id,
        }
        await client.cookie_manager.request(url, method="POST", params=params, json=json)

    @staticmethod
    def role_to_id(name: str) -> Optional[int]:
        if name == "派蒙":
            return -1
        return roleToId(name)

    @handler(CommandHandler, command="birthday_card", block=False)
    @handler(MessageHandler, filters=filters.Regex("^领取角色生日画片$"), block=False)
    async def command_birthday_card_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 领取生日画片命令请求", user.full_name, user.id)
        today_list = await self.get_today_birthday()
        if not today_list:
            reply_message = await message.reply_text("今天没有角色过生日哦~")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        try:
            client = await self.helper.get_genshin_client(user.id)
        except (CookiesNotFoundError, PlayerNotFoundError):
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_msg = await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙绑定账号",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML,
                )
                self.add_delete_message_job(reply_msg.chat_id, delay=30)
                self.add_delete_message_job(message, delay=30)
            else:
                await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙进行绑定",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            return
        if client.region == RegionEnum.HOYOLAB:
            text = "此功能当前只支持国服账号哦~"
        else:
            await fetch_hk4e_token_by_cookie(client)
            for name in today_list.copy():
                if role_id := self.role_to_id(name):
                    try:
                        await self.get_card(client, role_id)
                    except GenshinException as e:
                        if e.retcode in {-512008, -512009}:  # 未过生日、已领取过
                            today_list.remove(name)
            if today_list:
                text = f"成功领取了 {'、'.join(today_list)} 的生日画片~"
            else:
                text = "没有领取到生日画片哦 ~ 可能是已经领取过了"
        reply_message = await message.reply_text(text)
        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(message)
            self.add_delete_message_job(reply_message)
