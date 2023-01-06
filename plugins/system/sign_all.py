import datetime

from aiohttp import ClientConnectorError
from genshin import AlreadyClaimed, GenshinException, InvalidCookies
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, CommandHandler

from core.dependence.redisdb import RedisDB
from core.services.cookies import CookiesService
from core.plugin import Plugin, handler
from core.services.sign import SignServices
from core.services.sign.models import SignStatusEnum
from core.services.user import UserService
from plugins.genshin.sign import SignSystem
from plugins.jobs.sign import NeedChallenge
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import get_genshin_client
from utils.log import logger


class SignAll(Plugin):
    def __init__(
        self,
        sign_service: SignServices = None,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
        redis: RedisDB = None,
    ):
        self.sign_service = sign_service
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.sign_system = SignSystem(redis)

    @handler(CommandHandler, command="sign_all", block=False)
    @bot_admins_rights_check
    async def sign_all(self, update: Update, context: CallbackContext):
        user = update.effective_user
        logger.info(f"用户 {user.full_name}[{user.id}] sign_all 命令请求")
        message = update.effective_message
        reply = await message.reply_text("正在全部重新签到，请稍后...")
        sign_list = await self.sign_service.get_all()
        for sign_db in sign_list:
            user_id = sign_db.user_id
            old_status = sign_db.status
            try:
                client = await get_genshin_client(user_id)
                text = await self.sign_system.start_sign(client, is_sleep=True, is_raise=True, title="自动重新签到")
            except InvalidCookies:
                text = "自动签到执行失败，Cookie无效"
                sign_db.status = SignStatusEnum.INVALID_COOKIES
            except AlreadyClaimed:
                text = "今天旅行者已经签到过了~"
                sign_db.status = SignStatusEnum.ALREADY_CLAIMED
            except GenshinException as exc:
                text = f"自动签到执行失败，API返回信息为 {str(exc)}"
                sign_db.status = SignStatusEnum.GENSHIN_EXCEPTION
            except ClientConnectorError:
                text = "签到失败了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ "
                sign_db.status = SignStatusEnum.TIMEOUT_ERROR
            except NeedChallenge:
                text = "签到失败，触发验证码风控，自动签到自动关闭"
                sign_db.status = SignStatusEnum.NEED_CHALLENGE
            except Exception as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                text = "签到失败了呜呜呜 ~ 执行自动签到时发生错误"
            else:
                sign_db.status = SignStatusEnum.STATUS_SUCCESS
            if sign_db.chat_id < 0:
                text = f'<a href="tg://user?id={sign_db.user_id}">NOTICE {sign_db.user_id}</a>\n\n{text}'
            try:
                await context.bot.send_message(sign_db.chat_id, text, parse_mode=ParseMode.HTML)
            except BadRequest as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                sign_db.status = SignStatusEnum.BAD_REQUEST
            except Forbidden as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                sign_db.status = SignStatusEnum.FORBIDDEN
            except Exception as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                continue
            else:
                sign_db.status = SignStatusEnum.STATUS_SUCCESS
            sign_db.time_updated = datetime.datetime.now()
            if sign_db.status != old_status:
                await self.sign_service.update(sign_db)
        await reply.edit_text("全部账号重新签到完成")
