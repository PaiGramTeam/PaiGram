import re
from typing import TYPE_CHECKING

from telegram.ext import filters

from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.task.services import TaskCardServices
from core.services.users.services import UserService, UserAdminService
from metadata.genshin import AVATAR_DATA
from metadata.shortname import roleToId, roleToName
from plugins.tools.birthday_card import (
    BirthdayCardSystem,
    rm_starting_str,
)
from plugins.tools.genshin import GenshinHelper
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class BirthdayPlugin(Plugin):
    """Birthday."""

    def __init__(
        self,
        user_service: UserService,
        helper: GenshinHelper,
        cookie_service: CookiesService,
        card_system: BirthdayCardSystem,
        user_admin_service: UserAdminService,
        card_service: TaskCardServices,
    ):
        """Load Data."""
        self.user_service = user_service
        self.cookie_service = cookie_service
        self.helper = helper
        self.card_system = card_system
        self.user_admin_service = user_admin_service
        self.card_service = card_service

    @handler.command(command="birthday", block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        message = update.effective_message
        user = update.effective_user
        args = self.get_args(context)
        if len(args) >= 1:
            msg = args[0]
            logger.info("用户 %s[%s] 查询角色生日命令请求 || 参数 %s", user.full_name, user.id, msg)
            if re.match(r"\d{1,2}.\d{1,2}", msg):
                try:
                    month = rm_starting_str(re.findall(r"\d+", msg)[0], "0")
                    day = rm_starting_str(re.findall(r"\d+", msg)[1], "0")
                    key = f"{month}_{day}"
                    day_list = self.card_system.birthday_list.get(key, [])
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
            today_list = self.card_system.get_today_birthday()
            text = f"今天是 {'、'.join(today_list)} 的生日哦~" if today_list else "今天没有角色过生日哦~"
            reply_message = await message.reply_text(text)

        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(message)
            self.add_delete_message_job(reply_message)
