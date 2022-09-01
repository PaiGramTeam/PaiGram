import inspect
from typing import List, Dict

from utils.log import logger
from models.types import Func
from utils.aiobrowser import AioBrowser
from utils.manager import ModulesManager
from utils.mysql import MySQL
from utils.redisdb import RedisDB

ServicesFunctions: List[Func] = []
ServicesDict: Dict[str, Func] = {}


def listener_service():
    """监听服务"""

    def decorator(func: Func):
        ServicesFunctions.append(
            func
        )
        return func

    return decorator


class ServicesManager(ModulesManager):
    def __init__(self, mysql: MySQL, redis: RedisDB, browser: AioBrowser):
        super().__init__()
        self.browser = browser
        self.redis = redis
        self.mysql = mysql
        self.services_list: List[str] = []
        self.exclude_list: List[str] = []
        self.manager_name = "核心服务管理器"

    def add_service(self):
        for func in ServicesFunctions:
            if callable(func):
                kwargs = {}
                try:
                    signature = inspect.signature(func)
                except ValueError as exception:
                    if "no signature found" in str(exception):
                        logger.warning("no signature found", exception)
                        break
                    elif "not supported by signature" in str(exception):
                        logger.warning("not supported by signature", exception)
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
                    ServicesDict.setdefault(class_name, handlers_list)
                except BaseException as exc:
                    logger.error("初始化Service失败", exc)
                finally:
                    pass
