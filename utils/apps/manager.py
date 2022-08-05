import inspect
import os
from glob import glob
from importlib import import_module
from typing import List, Union, Dict

from logger import Log
from models.types import Func
from utils.aiobrowser import AioBrowser
from utils.mysql import MySQL
from utils.redisdb import RedisDB

ServiceFunctions: List[Func] = []
ServiceDict: Dict[str, Func] = {}


def listener_service():
    """监听服务"""

    def decorator(func: Func):
        ServiceFunctions.append(
            func
        )
        return func

    return decorator


class ServicesManager:
    def __init__(self, mysql: MySQL, redis: RedisDB, browser: AioBrowser):
        self.browser = browser
        self.redis = redis
        self.mysql = mysql
        self.app_list: List[str] = []
        self.exclude_list: List[str] = []

    def refresh_list(self, app_paths):
        self.app_list.clear()
        app_paths = glob(app_paths)
        for app_path in app_paths:
            if os.path.isdir(app_path):
                app_path = os.path.basename(app_path)
                self.app_list.append(app_path)

    def add_exclude(self, exclude: Union[str, List[str]]):
        if isinstance(exclude, str):
            self.exclude_list.append(exclude)
        elif isinstance(exclude, list):
            self.exclude_list.extend(exclude)
        else:
            raise TypeError

    def import_module(self):
        for app_name in self.app_list:
            if app_name not in self.exclude_list:
                try:
                    import_module(f"apps.{app_name}")
                except ImportError as exc:
                    Log.warning(f"Service模块 {app_name} 导入失败", exc)
                except ImportWarning as exc:
                    Log.warning(f"Service模块 {app_name} 加载成功但有警告", exc)
                except Exception as exc:
                    Log.warning(f"Service模块 {app_name} 加载失败", exc)
                else:
                    Log.debug(f"Service模块 {app_name} 加载成功")

    def add_service(self):
        for func in ServiceFunctions:
            if callable(func):
                kwargs = {}
                try:
                    signature = inspect.signature(func)
                except ValueError as exception:
                    if "no signature found" in str(exception):
                        Log.warning("no signature found", exception)
                        break
                    elif "not supported by signature" in str(exception):
                        Log.warning("not supported by signature", exception)
                        break
                    else:
                        raise exception
                else:
                    for parameter_name, parameter in signature.parameters.items():
                        annotation = parameter.annotation
                        if issubclass(annotation, MySQL):
                            kwargs[parameter_name] = self.mysql
                        if issubclass(annotation, RedisDB):
                            kwargs[parameter_name] = self.redis
                        if issubclass(annotation, AioBrowser):
                            kwargs[parameter_name] = self.browser
                try:
                    handlers_list = func(**kwargs)
                    class_name = handlers_list.__class__.__name__
                    ServiceDict.setdefault(class_name, handlers_list)
                except BaseException as exc:
                    Log.error("初始化Service失败", exc)
                finally:
                    pass
