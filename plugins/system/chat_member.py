import contextlib

from telegram import Update, Chat, User
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ChatMemberHandler

from core.admin.services import BotAdminService
from core.config import config, JoinGroups
from core.cookies.error import CookiesNotFoundError
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.user.error import UserNotFoundError
from core.user.services import UserService
from utils.chatmember import extract_status_change
from utils.decorators.error import error_callable
from utils.log import logger


class ChatMember(Plugin):
    def __init__(
        self,
        bot_admin_service: BotAdminService = None,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
    ):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.bot_admin_service = bot_admin_service

    @handler.chat_member(chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER, block=False)
    @error_callable
    async def track_chats(self, update: Update, context: CallbackContext) -> None:
        result = extract_status_change(update.my_chat_member)
        if result is None:
            return
        was_member, is_member = result
        user = update.effective_user
        chat = update.effective_chat
        if chat.type == Chat.PRIVATE:
            if not was_member and is_member:
                logger.info("用户 %s[%s] 启用了机器人", user.full_name, user.id)
            elif was_member and not is_member:
                logger.info("用户 %s[%s] 屏蔽了机器人", user.full_name, user.id)
        elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            if not was_member and is_member:
                logger.info("用户 %s[%s] 邀请BOT进入群 %s[%s]", user.full_name, user.id, chat.title, chat.id)
                await self.greet(user, chat, context)
            elif was_member and not is_member:
                logger.info("用户 %s[%s] 从 %s[%s] 群移除Bot", user.full_name, user.id, chat.title, chat.id)
        else:
            if not was_member and is_member:
                logger.info("用户 %s[%s] 邀请BOT进入频道 %s[%s]", user.full_name, user.id, chat.title, chat.id)
            elif was_member and not is_member:
                logger.info("用户 %s[%s] 从 %s[%s] 频道移除Bot", user.full_name, user.id, chat.title, chat.id)

    async def greet(self, user: User, chat: Chat, context: CallbackContext) -> None:
        quit_status = True
        if config.join_groups == JoinGroups.NO_ALLOW:
            try:
                admin_list = await self.bot_admin_service.get_admin_list()
                if user.id in admin_list:
                    quit_status = False
                else:
                    logger.warning("不是管理员邀请！退出群聊")
            except Exception as exc:  # pylint: disable=W0703
                logger.error("获取信息出现错误", exc_info=exc)
        elif config.join_groups == JoinGroups.ALLOW_AUTH_USER:
            try:
                user_info = await self.user_service.get_user_by_id(user.id)
                await self.cookies_service.get_cookies(user.id, user_info.region)
            except (UserNotFoundError, CookiesNotFoundError):
                logger.warning("用户 %s[%s] 邀请请求被拒绝", user.full_name, user.id)
            except Exception as exc:
                logger.error("获取信息出现错误", exc_info=exc)
            else:
                quit_status = False
        elif config.join_groups == JoinGroups.ALLOW_USER:
            try:
                await self.user_service.get_user_by_id(user.id)
            except UserNotFoundError:
                logger.warning("用户 %s[%s] 邀请请求被拒绝", user.full_name, user.id)
            except Exception as exc:
                logger.error("获取信息出现错误", exc_info=exc)
            else:
                quit_status = False
        elif config.join_groups == JoinGroups.ALLOW_ALL:
            quit_status = False
        else:
            quit_status = True
        if quit_status:
            with contextlib.suppress(BadRequest):
                await context.bot.send_message(chat.id, "派蒙不想进去！不是旅行者的邀请！")
            await context.bot.leave_chat(chat.id)
        else:
            await context.bot.send_message(chat.id, "感谢邀请小派蒙到本群！请使用 /help 查看咱已经学会的功能。")
