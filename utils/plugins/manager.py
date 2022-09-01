from typing import List

from telegram.ext import Application

from utils.log import logger
from utils.manager import ModulesManager

PluginsClass: List[object] = []


def listener_plugins_class():
    """监听插件
    :return: None
    """

    def decorator(func: object):
        PluginsClass.append(func)
        return func

    return decorator


class PluginsManager(ModulesManager):

    def __init__(self):
        super().__init__()
        self.manager_name = "插件管理器"

    @staticmethod
    def add_handler(application: Application):
        for func in PluginsClass:
            if callable(func):
                try:
                    handlers_list = func.create_handlers()
                    for handler in handlers_list:
                        application.add_handler(handler)
                except AttributeError as exc:
                    if "create_handlers" in str(exc):
                        logger.error("创建 handlers 函数未找到", exc)
                    logger.error("初始化Class失败", exc)
                except BaseException as exc:
                    logger.error("初始化Class失败", exc)
                finally:
                    pass
