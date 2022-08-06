import datetime
import time

from aiohttp import ClientConnectorError
from genshin import Game, GenshinException, AlreadyClaimed, InvalidCookies
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, JobQueue

from apps.cookies import CookiesService
from apps.sign.models import SignStatusEnum
from apps.sign.services import SignServices
from apps.user import UserService
from config import config
from logger import Log
from utils.apps.inject import inject
from utils.helpers import get_genshin_client
from utils.job.manager import listener_jobs_class


@listener_jobs_class()
class SignJob:

    @inject
    def __init__(self, sign_service: SignServices = None, user_service: UserService = None,
                 cookies_service: CookiesService = None):
        self.sign_service = sign_service
        self.cookies_service = cookies_service
        self.user_service = user_service

    @classmethod
    def build_jobs(cls, job_queue: JobQueue):
        sign = cls()
        if config.DEBUG:
            job_queue.run_once(sign.sign, 3, name="SignJobTest")
        # 每天凌晨一点执行
        job_queue.run_daily(sign.sign, datetime.time(hour=1, minute=0, second=0), name="SignJob")

    async def sign(self, context: CallbackContext):
        Log.info("正在执行自动签到")
        sign_list = await self.sign_service.get_all()
        for sign_db in sign_list:
            if sign_db.status != SignStatusEnum.STATUS_SUCCESS:
                continue
            user_id = sign_db.user_id
            try:
                client = await get_genshin_client(user_id, self.user_service, self.cookies_service)
                rewards = await client.get_monthly_rewards(game=Game.GENSHIN, lang="zh-cn")
                daily_reward_info = await client.get_reward_info(game=Game.GENSHIN)
                if not daily_reward_info.signed_in:
                    request_daily_reward = await client.request_daily_reward("sign", method="POST", game=Game.GENSHIN)
                    Log.info(f"UID {client.uid} 签到请求 {request_daily_reward}")
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
                text = f"########### 定时签到 ###########\n" \
                       f"#### {today} (UTC+8) ####\n" \
                       f"UID: {client.uid}\n" \
                       f"今日奖励: {reward.name} × {reward.amount}\n" \
                       f"本月漏签次数：{missed_days}\n" \
                       f"签到结果: {result}"
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
            except BaseException as exc:
                Log.error(f"执行自动签到时发生错误", exc)
                continue
            try:
                await context.bot.send_message(sign_db.chat_id, text)
            except BadRequest as exc:
                Log.error(f"执行自动签到时发生错误", exc)
                sign_db.status = SignStatusEnum.BAD_REQUEST
            except Forbidden as exc:
                Log.error(f"执行自动签到时发生错误", exc)
                sign_db.status = SignStatusEnum.FORBIDDEN
            except BaseException as exc:
                Log.error(f"执行自动签到时发生错误", exc)
                continue
            sign_db.time_updated = datetime.datetime.now()
            await self.sign_service.update(sign_db)
        Log.info("执行自动签到完成")
