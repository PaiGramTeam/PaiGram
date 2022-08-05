import datetime

from telegram.ext import CallbackContext, JobQueue

from apps.cookies.services import PublicCookiesService
from logger import Log
from utils.apps.inject import inject
from utils.job.manager import listener_jobs_class


@listener_jobs_class()
class PublicCookies:

    @inject
    def __init__(self, public_cookies_service: PublicCookiesService):
        self.public_cookies_service = public_cookies_service

    @classmethod
    def build_jobs(cls, job_queue: JobQueue):
        jobs = cls()
        job_queue.run_repeating(jobs.refresh, datetime.timedelta(hours=2))

    async def refresh(self, _: CallbackContext):
        Log.info("正在刷新公共Cookies池")
        await self.public_cookies_service.refresh()
        Log.info("刷新公共Cookies池成功")
