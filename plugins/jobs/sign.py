import datetime

from aiohttp import ClientConnectorError
from genshin import GenshinException, AlreadyClaimed, InvalidCookies
from httpx import TimeoutException
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext

from core.base.redisdb import RedisDB
from core.cookies import CookiesService
from core.plugin import Plugin, job
from core.sign.models import SignStatusEnum
from core.sign.services import SignServices
from core.user import UserService
from plugins.genshin.sign import SignSystem
from plugins.system.errorhandler import notice_chat_id
from plugins.system.sign_status import SignStatus
from utils.log import logger


class NeedChallenge(Exception):
    pass


class SignJob(Plugin):
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

    @job.run_daily(time=datetime.time(hour=0, minute=1, second=0), name="SignJob")
    async def sign(self, context: CallbackContext):
        logger.info("正在执行自动签到" if context.job.name == "SignJob" else "正在执行自动重签")
        sign_list = await self.sign_service.get_all()
        for sign_db in sign_list:
            user_id = sign_db.user_id
            if sign_db.status in [
                SignStatusEnum.INVALID_COOKIES,
                SignStatusEnum.FORBIDDEN,
                SignStatusEnum.NEED_CHALLENGE,
            ]:
                continue
            if context.job.name == "SignJob":
                if sign_db.status not in [SignStatusEnum.STATUS_SUCCESS, SignStatusEnum.ALREADY_CLAIMED]:
                    continue
            elif context.job.name == "SignAgainJob":
                if sign_db.status in [SignStatusEnum.STATUS_SUCCESS, SignStatusEnum.ALREADY_CLAIMED]:
                    continue
            try:
                text = await self.sign_system.start_sign(
                    user_id, is_sleep=True, is_raise=True, title="自动签到" if context.job.name == "SignJob" else "自动重新签到"
                )
                sign_db.status = SignStatusEnum.STATUS_SUCCESS
            except InvalidCookies:
                text = "自动签到执行失败，Cookie无效"
                sign_db.status = SignStatusEnum.INVALID_COOKIES
            except AlreadyClaimed:
                text = "今天旅行者已经签到过了~"
                sign_db.status = SignStatusEnum.ALREADY_CLAIMED
            except GenshinException as exc:
                text = f"自动签到执行失败，API返回信息为 {str(exc)}"
                sign_db.status = SignStatusEnum.GENSHIN_EXCEPTION
            except TimeoutException:
                text = "签到失败了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ "
                sign_db.status = SignStatusEnum.TIMEOUT_ERROR
            except ClientConnectorError as exc:
                logger.warning(f"aiohttp 请求错误 {repr(exc)}")
                text = "签到失败了呜呜呜 ~ 链接服务器发生错误 服务器熟啦 ~ "
                sign_db.status = SignStatusEnum.TIMEOUT_ERROR
            except NeedChallenge:
                text = "签到失败，触发验证码风控，自动签到自动关闭"
                sign_db.status = SignStatusEnum.NEED_CHALLENGE
            except Exception as exc:
                logger.error(f"执行自动签到时发生错误 用户UID[{user_id}]")
                logger.exception(exc)
                text = "签到失败了呜呜呜 ~ 执行自动签到时发生错误"
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
            sign_db.time_updated = datetime.datetime.now()
            await self.sign_service.update(sign_db)
        logger.info("执行自动签到完成" if context.job.name == "SignJob" else "执行自动重签完成")
        if context.job.name == "SignJob":
            context.job_queue.run_once(self.sign, when=60, name="SignAgainJob")
        elif context.job.name == "SignAgainJob":
            text = await SignStatus.get_sign_status(self.sign_service)
            await context.bot.send_message(notice_chat_id, text, parse_mode=ParseMode.HTML)
