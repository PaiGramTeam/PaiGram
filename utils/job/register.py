from telegram.ext import Application

from utils.log import logger
from utils.job.manager import JobsManager


def register_job(application: Application):
    logger.info("正在加载Job管理器")
    jobs_manager = JobsManager()

    jobs_manager.refresh_list("jobs/*")

    # 忽略内置模块
    jobs_manager.add_exclude(["base"])

    logger.info("Job管理器正在加载插件")
    jobs_manager.import_module()
    jobs_manager.add_handler(application)

    logger.info("Job加载成功")
