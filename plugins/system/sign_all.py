import datetime
import asyncio

from aiohttp import ClientConnectorError
from genshin import InvalidCookies, AlreadyClaimed, GenshinException
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import CommandHandler, CallbackContext

from core.cookies import CookiesService
from core.plugin import Plugin, handler
from core.sign import SignServices
from core.sign.models import SignStatusEnum
from core.user import UserService
from plugins.jobs.sign import NeedChallenge, SignJob
from utils.decorators.admins import bot_admins_rights_check
from utils.log import logger


class SignAll(Plugin):
    def __init__(
        self,
        sign_service: SignServices = None,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
    ):
        self.sign_service = sign_service
        self.cookies_service = cookies_service
        self.user_service = user_service

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
                text = await SignJob.single_sign(user_id)
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
            except BaseException as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                text = "签到失败了呜呜呜 ~ 执行自动签到时发生错误"
            if sign_db.chat_id < 0:
                text = f'<a href="tg://user?id={sign_db.user_id}">NOTICE {sign_db.user_id}</a>\n\n{text}'
            try:
                if "今天旅行者已经签到过了~" not in text:
                    await context.bot.send_message(sign_db.chat_id, text, parse_mode=ParseMode.HTML)
                    await asyncio.sleep(5)  # 回复延迟5S避免触发洪水防御
            except BadRequest as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                sign_db.status = SignStatusEnum.BAD_REQUEST
            except Forbidden as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                sign_db.status = SignStatusEnum.FORBIDDEN
            except BaseException as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                continue
            sign_db.time_updated = datetime.datetime.now()
            if sign_db.status != old_status:
                await self.sign_service.update(sign_db)
        await reply.edit_text("全部账号重新签到完成")
