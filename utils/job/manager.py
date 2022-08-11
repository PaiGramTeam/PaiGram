from typing import List

from telegram.ext import Application

from logger import Log
from utils.manager import ModulesManager

JobsClass: List[object] = []


def listener_jobs_class():
    """监听JOB
    :return: None
    """

    def decorator(func: object):
        JobsClass.append(func)
        return func

    return decorator


class JobsManager(ModulesManager):
    def __init__(self):
        super().__init__()
        self.job_list: List[str] = []  # 用于存储文件名称
        self.exclude_list: List[str] = []
        self.manager_name = "定时任务管理器"

    @staticmethod
    def add_handler(application: Application):
        for func in JobsClass:
            if callable(func):
                try:
                    func.build_jobs(application.job_queue)
                    # Log.info(f"添加每日Job成功 Job名称[{handler.name}] Job每日执行时间[{handler.time.isoformat()}]")
                except AttributeError as exc:
                    if "build_jobs" in str(exc):
                        Log.error("build_jobs 函数未找到", exc)
                    Log.error("初始化Class失败", exc)
                except BaseException as exc:
                    Log.error("初始化Class失败", exc)
                finally:
                    pass
