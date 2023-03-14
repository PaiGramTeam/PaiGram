from telegram import Chat, Update, User
from telegram.error import NetworkError
from telegram.ext import CallbackContext, ChatMemberHandler

from core.config import JoinGroups, config
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.users.services import UserAdminService
from utils.chatmember import extract_status_change
from utils.log import logger


class ChatMember(Plugin):
    def __init__(
        self,
        user_admin_service: UserAdminService = None,
        players_service: PlayersService = None,
        cookies_service: CookiesService = None,
    ):
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.user_admin_service = user_admin_service

    @handler.chat_member(chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER, block=False)
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
                if await self.user_admin_service.is_admin(user.id):
                    quit_status = False
                else:
                    logger.warning("不是管理员邀请！退出群聊")
            except Exception as exc:  # pylint: disable=W0703
                logger.error("获取信息出现错误", exc_info=exc)
        elif config.join_groups == JoinGroups.ALLOW_AUTH_USER:
            try:
                if await self.cookies_service.get(user.id) is not None:
                    quit_status = False
            except Exception as exc:  # pylint: disable=W0703
                logger.error("获取信息出现错误", exc_info=exc)
        elif config.join_groups == JoinGroups.ALLOW_USER:
            try:
                if await self.players_service.get(user.id) is not None:
                    quit_status = False
            except Exception as exc:  # pylint: disable=W0703
                logger.error("获取信息出现错误", exc_info=exc)
        elif config.join_groups == JoinGroups.ALLOW_ALL:
            quit_status = False
        else:
            quit_status = True
        if quit_status:
            try:
                await context.bot.send_message(chat.id, "派蒙不想进去！不是旅行者的邀请！")
            except NetworkError as exc:
                logger.info("发送消息失败 %s", exc.message)
            except Exception as exc:
                logger.info("发送消息失败", exc_info=exc)
            await context.bot.leave_chat(chat.id)
        else:
            await context.bot.send_message(chat.id, "感谢邀请小派蒙到本群！请使用 /help 查看咱已经学会的功能。")
