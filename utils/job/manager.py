import os
from glob import glob
from importlib import import_module
from os import path
from typing import List, Union

from telegram.ext import Application

from jobs.base import RunDailyHandler
from logger import Log

JobsClass: List[object] = []


def listener_jobs_class():
    """监听JOB
    :return: None
    """

    def decorator(func: object):
        JobsClass.append(func)
        return func

    return decorator


class JobsManager:
    def __init__(self):
        self.job_list: List[str] = []  # 用于存储文件名称
        self.exclude_list: List[str] = []

    def refresh_list(self, plugin_paths):
        self.job_list.clear()
        plugin_paths = glob(plugin_paths)
        for plugin_path in plugin_paths:
            if plugin_path.startswith('__'):
                continue
            module_name = path.basename(path.normpath(plugin_path))
            root, ext = os.path.splitext(module_name)
            if ext == ".py":
                self.job_list.append(root)

    def add_exclude(self, exclude: Union[str, List[str]]):
        if isinstance(exclude, str):
            self.exclude_list.append(exclude)
        elif isinstance(exclude, list):
            self.exclude_list.extend(exclude)
        else:
            raise TypeError

    def import_module(self):
        for job_name in self.job_list:
            if job_name not in self.exclude_list:
                try:
                    import_module(f"jobs.{job_name}")
                except ImportError as exc:
                    Log.warning(f"Job模块 {job_name} 导入失败", exc)
                except ImportWarning as exc:
                    Log.warning(f"Job模块 {job_name} 加载成功但有警告", exc)
                except BaseException as exc:
                    Log.warning(f"Job模块 {job_name} 加载失败", exc)
                else:
                    Log.debug(f"Job模块 {job_name} 加载成功")

    @staticmethod
    def add_handler(application: Application):
        for func in JobsClass:
            if callable(func):
                try:
                    handlers_list = func.build_jobs()
                    for handler in handlers_list:
                        if isinstance(handler, RunDailyHandler):
                            application.job_queue.run_daily(**handler.get_kwargs)
                            Log.info(f"添加每日Job成功 Job名称[{handler.name}] Job每日执行时间[{handler.time.isoformat()}]")
                except AttributeError as exc:
                    if "build_jobs" in str(exc):
                        Log.error("build_jobs 函数未找到", exc)
                    Log.error("初始化Class失败", exc)
                except BaseException as exc:
                    Log.error("初始化Class失败", exc)
                finally:
                    pass
