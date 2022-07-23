import inspect
import os
from glob import glob
from importlib import import_module
from typing import List, Union, Dict

from logger import Log
from model.types import Func

ServiceFunctions: List[Func] = []
ServiceDict: Dict[str, Func] = {}


def listener_service():
    """监听服务

    :return: None
    """

    def decorator(func: Func):
        ServiceFunctions.append(
            func
        )
        return func

    return decorator


class JobsManager:
    def __init__(self):
        self.app_list: List[str] = []  # 用于存储文件名称
        self.exclude_list: List[str] = []

    def refresh_list(self, app_paths):
        self.app_list.clear()
        app_paths = glob(app_paths)
        for app_path in app_paths:
            if os.path.isdir(app_path):
                self.app_list.append(app_path)

    def add_exclude(self, exclude: Union[str, List[str]]):
        if isinstance(exclude, str):
            self.exclude_list.append(exclude)
        elif isinstance(exclude, list):
            self.exclude_list.extend(exclude)
        else:
            raise TypeError

    def import_module(self):
        for job_name in self.app_list:
            if job_name not in self.exclude_list:
                try:
                    import_module(job_name)
                except ImportError as exc:
                    Log.warning(f"Job模块 {job_name} 导入失败", exc)
                except ImportWarning as exc:
                    Log.warning(f"Job模块 {job_name} 加载成功但有警告", exc)
                except Exception as exc:
                    Log.warning(f"Job模块 {job_name} 加载失败", exc)
                else:
                    Log.debug(f"Job模块 {job_name} 加载成功")

    @staticmethod
    def add_service():
        for func in ServiceFunctions:
            if callable(func):
                try:
                    handlers_list = func()
                    full_args_pec = inspect.getfullargspec(handlers_list)
                    class_name = full_args_pec.__class__.__name__
                    ServiceDict.setdefault(class_name, handlers_list)
                except Exception as exc:
                    Log.error("初始化Service失败", exc)
                finally:
                    pass
