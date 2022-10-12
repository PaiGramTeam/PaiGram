import asyncio
import datetime
import secrets
import time

from aiohttp import ClientConnectorError
from genshin import Game, GenshinException, AlreadyClaimed, InvalidCookies
from httpx import TimeoutException
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext

from core.cookies import CookiesService
from core.plugin import Plugin, job
from core.sign.models import SignStatusEnum
from core.sign.services import SignServices
from core.user import UserService
from plugins.genshin.sign import Sign
from utils.helpers import get_genshin_client
from utils.log import logger


class NeedChallenge(Exception):
    pass


class SignJob(Plugin):
    def __init__(
            self,
            sign_service: SignServices = None,
            user_service: UserService = None,
            cookies_service: CookiesService = None,
    ):
        self.sign_service = sign_service
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.random = secrets.SystemRandom()

    @staticmethod
    async def single_sign(user_id: int) -> str:
        client = await get_genshin_client(user_id)
        rewards = await client.get_monthly_rewards(game=Game.GENSHIN, lang="zh-cn")
        daily_reward_info = await client.get_reward_info(game=Game.GENSHIN)
        if not daily_reward_info.signed_in:
            request_daily_reward = await client.request_daily_reward("sign", method="POST", game=Game.GENSHIN)
            if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                headers = await Sign.pass_challenge(
                    request_daily_reward.get("gt", ""),
                    request_daily_reward.get("challenge", ""),
                )
                if not headers:
                    logger.warning(f"UID {client.uid} 签到失败，触发验证码风控")
                    raise NeedChallenge
                request_daily_reward = await client.request_daily_reward(
                    "sign",
                    method="POST",
                    game=Game.GENSHIN,
                    lang="zh-cn",
                    headers=headers,
                )
                if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                    logger.warning(f"UID {client.uid} 签到失败，触发验证码风控")
                    raise NeedChallenge
                logger.info(f"UID {client.uid} 签到请求 {request_daily_reward} | 签到成功")
            else:
                logger.info(f"UID {client.uid} 签到请求 {request_daily_reward}")
            result = "OK"
        else:
            result = "今天旅行者已经签到过了~"
        reward = rewards[daily_reward_info.claimed_rewards - (1 if daily_reward_info.signed_in else 0)]
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cn_timezone = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(cn_timezone)
        missed_days = now.day - daily_reward_info.claimed_rewards
        if not daily_reward_info.signed_in:
            missed_days -= 1
        return (
            f"########### 定时签到 ###########\n"
            f"#### {today} (UTC+8) ####\n"
            f"UID: {client.uid}\n"
            f"今日奖励: {reward.name} × {reward.amount}\n"
            f"本月漏签次数：{missed_days}\n"
            f"签到结果: {result}"
        )

    @job.run_daily(time=datetime.time(hour=0, minute=1, second=0), name="SignJob")
    async def sign(self, context: CallbackContext):
        if context.job.name == "SignJob":
            logger.info("正在执行自动签到")
        if context.job.name == "SignAgainJob":
            logger.info("正在执行自动重签")
        sign_list = await self.sign_service.get_all()
        for sign_db in sign_list:
            user_id = sign_db.user_id
            if sign_db.status != SignStatusEnum.STATUS_SUCCESS:
                if sign_db.status == SignStatusEnum.TIMEOUT_ERROR:
                    if context.job.name == "SignAgainJob":
                        logger.info(f"用户 [{user_id}] 即将执行重签")
                else:
                    continue
            try:
                text = await self.single_sign(user_id)
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
            if sign_db.chat_id < 0:
                text = f'<a href="tg://user?id={sign_db.user_id}">NOTICE {sign_db.user_id}</a>\n\n{text}'
            try:
                await context.bot.send_message(sign_db.chat_id, text, parse_mode=ParseMode.HTML)
                await asyncio.sleep(10 + self.random.random() * 50)  # 回复延迟 [10, 60) 避免触发洪水防御
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
        logger.info("执行自动签到完成")
        context.job_queue.run_once(self.sign, when=datetime.time(hour=0, minute=1, second=0), name="SignAgainJob")
