from telegram import Update
from telegram.ext import CallbackContext

from core.admin.services import BotAdminService
from core.config import config, JoinGroups
from core.cookies.error import CookiesNotFoundError
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.user.error import UserNotFoundError
from core.user.services import UserService
from utils.log import logger


class BotJoiningGroupsVerification(Plugin):
    def __init__(
        self,
        bot_admin_service: BotAdminService = None,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
    ):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.bot_admin_service = bot_admin_service

    @handler.message.new_chat_members(priority=1)
    async def new_member(self, update: Update, context: CallbackContext) -> None:
        if config.join_groups == JoinGroups.ALLOW_ALL:
            return None
        message = update.effective_message
        chat = message.chat
        from_user = message.from_user
        for new_chat_members_user in message.new_chat_members:
            if new_chat_members_user.id == context.bot.id:
                logger.info(f"有人邀请BOT进入群 {chat.title}[{chat.id}]")
                quit_status = True
                if from_user is not None:
                    logger.info(f"用户 {from_user.full_name}[{from_user.id}] 在群 {chat.title}[{chat.id}] 邀请BOT")
                    if config.join_groups == JoinGroups.NO_ALLOW:
                        try:
                            admin_list = await self.bot_admin_service.get_admin_list()
                            if from_user.id in admin_list:
                                quit_status = False
                            else:
                                logger.warning("不是管理员邀请！退出群聊")
                        except Exception as exc:
                            logger.error(f"获取信息出现错误 {repr(exc)}")
                    elif config.join_groups == JoinGroups.ALLOW_AUTH_USER:
                        try:
                            user_info = await self.user_service.get_user_by_id(from_user.id)
                            await self.cookies_service.get_cookies(from_user.id, user_info.region)
                        except (UserNotFoundError, CookiesNotFoundError):
                            logger.warning(f"用户 {from_user.full_name}[{from_user.id}] 邀请请求被拒绝")
                        except Exception as exc:
                            logger.error(f"获取信息出现错误 {repr(exc)}")
                        else:
                            quit_status = False
                    else:
                        quit_status = True
                else:
                    logger.info(f"未知用户 在群 {chat.title}[{chat.id}] 邀请BOT")
                if quit_status:
                    await context.bot.send_message(message.chat_id, "派蒙不想进去！不是旅行者的邀请！")
                    await context.bot.leave_chat(chat.id)
                else:
                    await context.bot.send_message(message.chat_id, "感谢邀请小派蒙到本群！请使用 /help 查看咱已经学会的功能。")
