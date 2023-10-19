import re
from typing import TYPE_CHECKING

from simnet import Region
from simnet.errors import RegionNotSupported
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import filters, MessageHandler, CommandHandler
from telegram.helpers import create_deep_linked_url

from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.task.models import Task as TaskUser, TaskStatusEnum
from core.services.task.services import TaskCardServices
from core.services.users.services import UserService, UserAdminService
from metadata.genshin import AVATAR_DATA
from metadata.shortname import roleToId, roleToName
from plugins.tools.birthday_card import (
    BirthdayCardSystem,
    rm_starting_str,
    BirthdayCardNoBirthdayError,
    BirthdayCardAlreadyClaimedError,
)
from plugins.tools.genshin import PlayerNotFoundError, CookiesNotFoundError, GenshinHelper
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
        self.track_event(update, "birthday")

    async def _process_auto_birthday_card(self, user_id: int, chat_id: int, method: str) -> str:
        try:
            async with self.helper.genshin(user_id) as client:
                if client.region != Region.CHINESE:
                    return "此功能当前只支持国服账号哦~"
        except (PlayerNotFoundError, CookiesNotFoundError):
            return "未查询到账号信息，请先私聊派蒙绑定账号"
        user: TaskUser = await self.card_service.get_by_user_id(user_id)
        if user:
            if method == "关闭":
                await self.card_service.remove(user)
                return "关闭自动领取生日画片成功"
            if method == "开启":
                if user.chat_id == chat_id:
                    return "自动领取生日画片已经开启过了"
                user.chat_id = chat_id
                user.status = TaskStatusEnum.STATUS_SUCCESS
                await self.card_service.update(user)
                return "修改自动领取生日画片对话成功"
        elif method == "关闭":
            return "您还没有开启自动领取生日画片"
        elif method == "开启":
            user = self.card_service.create(user_id, chat_id, TaskStatusEnum.STATUS_SUCCESS)
            await self.card_service.add(user)
            return "开启自动领取生日画片成功"

    @handler(CommandHandler, command="birthday_card", block=False)
    @handler(MessageHandler, filters=filters.Regex("^领取角色生日画片$"), block=False)
    async def command_birthday_card_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        message = update.effective_message
        user = update.effective_user
        args = self.get_args(context)
        if len(args) >= 1:
            msg = None
            if args[0] == "开启自动领取":
                if await self.user_admin_service.is_admin(user.id):
                    msg = await self._process_auto_birthday_card(user.id, message.chat_id, "开启")
                else:
                    msg = await self._process_auto_birthday_card(user.id, user.id, "开启")
            elif args[0] == "关闭自动领取":
                msg = await self._process_auto_birthday_card(user.id, message.chat_id, "关闭")
            if msg:
                logger.info("用户 %s[%s] 自动领取生日画片命令请求 || 参数 %s", user.full_name, user.id, args[0])
                reply_message = await message.reply_text(msg)
                if filters.ChatType.GROUPS.filter(message):
                    self.add_delete_message_job(reply_message, delay=30)
                    self.add_delete_message_job(message, delay=30)
                return
        logger.info("用户 %s[%s] 领取生日画片命令请求", user.full_name, user.id)
        try:
            async with self.helper.genshin(user.id) as client:
                try:
                    text = await self.card_system.start_get_card(client)
                except RegionNotSupported:
                    text = "此功能当前只支持国服账号哦~"
                except BirthdayCardNoBirthdayError:
                    text = "今天没有角色过生日哦~"
                except BirthdayCardAlreadyClaimedError:
                    text = "没有领取到生日画片哦 ~ 可能是已经领取过了"
                reply_message = await message.reply_text(text)
                if filters.ChatType.GROUPS.filter(reply_message):
                    self.add_delete_message_job(message)
                    self.add_delete_message_job(reply_message)
                self.track_event(update, "birthday_card")
        except (CookiesNotFoundError, PlayerNotFoundError):
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
            return
