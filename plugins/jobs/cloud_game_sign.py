import datetime
from typing import TYPE_CHECKING

from core.plugin import Plugin, job
from modules.errorpush import SentryClient
from plugins.tools.cloud_game import CloudGameHelper
from plugins.tools.sign import SignJobType
from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import ContextTypes


class SignJob(Plugin):
    def __init__(self, sign_system: CloudGameHelper):
        self.sign_system = sign_system

    @job.run_daily(time=datetime.time(hour=5, minute=1, second=0), name="CloudGameSignJob")
    @SentryClient.monitor(monitor_slug="CloudGameSignJob")
    async def sign(self, context: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行云游戏自动签到")
        await self.sign_system.do_sign_job(context, job_type=SignJobType.START)
        logger.success("执行云游戏自动签到完成")
        await self.re_sign(context)

    async def re_sign(self, context: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行云游戏自动重签")
        await self.sign_system.do_sign_job(context, job_type=SignJobType.REDO)
        logger.success("执行云游戏自动重签完成")
