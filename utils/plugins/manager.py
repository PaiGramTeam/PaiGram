import os
from glob import glob
from importlib import import_module
from os import path
from typing import List, Union, Tuple

from telegram.ext import Application

from jobs.base import RunDailyHandler
from logger import Log
from service import BaseService

PluginsClass: List[Tuple[object, dict]] = []
JobsClass: List[Tuple[object, dict]] = []


def listener_plugins_class(need_service: bool = False):
    """监听插件

    :param need_service: 插件类中 create_handlers 函数是否传入 service
    :return: None
    """
    plugin_info = {
        "need_service": need_service
    }

    def decorator(func: object):
        PluginsClass.append(
            (func, plugin_info)
        )
        return func

    return decorator


def listener_jobs_class(need_service: bool = False):
    """监听JOB

    :param need_service: 插件类中 create_handlers 函数是否传入 service
    :return: None
    """
    job_info = {
        "need_service": need_service
    }

    def decorator(func: object):
        JobsClass.append(
            (func, job_info)
        )
        return func

    return decorator


class PluginsManager:
    def __init__(self):
        self.plugin_list: List[str] = []  # 用于存储文件名称
        self.exclude_list: List[str] = []

    def refresh_list(self, plugin_paths):
        self.plugin_list.clear()
        plugin_paths = glob(plugin_paths)
        for plugin_path in plugin_paths:
            if plugin_path.startswith('__'):
                continue
            module_name = path.basename(path.normpath(plugin_path))
            root, ext = os.path.splitext(module_name)
            if ext == ".py":
                self.plugin_list.append(root)

    def add_exclude(self, exclude: Union[str, List[str]]):
        if isinstance(exclude, str):
            self.exclude_list.append(exclude)
        elif isinstance(exclude, list):
            self.exclude_list.extend(exclude)
        else:
            raise TypeError

    def import_module(self):
        for plugin_name in self.plugin_list:
            if plugin_name not in self.exclude_list:
                try:
                    import_module(f"plugins.{plugin_name}")
                except ImportError as exc:
                    Log.warning(f"插件 {plugin_name} 导入失败", exc)
                except ImportWarning as exc:
                    Log.warning(f"插件 {plugin_name} 加载成功但有警告", exc)
                except BaseException as exc:
                    Log.warning(f"插件 {plugin_name} 加载失败", exc)
                else:
                    Log.debug(f"插件 {plugin_name} 加载成功")

    @staticmethod
    def add_handler(application: Application, service: BaseService):
        for pc in PluginsClass:
            func = pc[0]
            plugin_info = pc[1]
            # 构建 kwargs
            kwargs = {}
            if plugin_info.get("need_service", False):
                kwargs["service"] = service
            if callable(func):
                try:
                    handlers_list = func.create_handlers(**kwargs)
                    for handler in handlers_list:
                        application.add_handler(handler)
                except AttributeError as exc:
                    if "create_handlers" in str(exc):
                        Log.error("创建 handlers 函数未找到", exc)
                    Log.error("初始化Class失败", exc)
                except BaseException as exc:
                    Log.error("初始化Class失败", exc)
                finally:
                    pass


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
    def add_handler(application: Application, service: BaseService):
        for pc in JobsClass:
            func = pc[0]
            plugin_info = pc[1]
            # 构建 kwargs
            kwargs = {}
            if plugin_info.get("need_service", False):
                kwargs["service"] = service
            if callable(func):
                try:
                    handlers_list = func.build_jobs(**kwargs)
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
