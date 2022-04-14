import logging
from logging.handlers import RotatingFileHandler  # 按文件大小滚动备份
import colorlog  # 控制台日志输入颜色
import os

cur_path = os.path.realpath(os.getcwd())  # log_path是存放日志的路径
log_path = os.path.join(cur_path, 'logs')
if not os.path.exists(log_path):
    os.mkdir(log_path)  # 如果不存在这个logs文件夹，就自动创建一个
logName = os.path.join(log_path, 'log.log')  # 文件的命名

log_colors_config = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red',
}


class Logger:
    def __init__(self):
        self.logName = logName
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        # self.formatter = colorlog.ColoredFormatter( '%(log_color)s[%(asctime)s] [%(filename)s:%(lineno)d] [%(
        # module)s:%(funcName)s] [%(levelname)s] - %(message)s', log_colors=log_colors_config)
        self.formatter = colorlog.ColoredFormatter(
            '%(log_color)s[%(asctime)s] [%(levelname)s] - %(message)s', log_colors=log_colors_config)
        self.formatter2 = colorlog.ColoredFormatter(
            '[%(asctime)s] [%(levelname)s] - %(message)s')

    def getLogger(self):
        return self.logger

    def __console(self, level, message, exc_info=None):
        # 创建一个FileHandler，用于写到本地
        fh = RotatingFileHandler(filename=self.logName, maxBytes=1024 * 1024 * 5, backupCount=5,
                                 encoding='utf-8')  # 使用RotatingFileHandler类，滚动备份日志
        fh.setLevel(logging.INFO)
        fh.setFormatter(self.formatter2)
        self.logger.addHandler(fh)

        ch = colorlog.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(self.formatter)
        self.logger.addHandler(ch)

        if level == 'info':
            self.logger.info(msg=message, exc_info=exc_info)
        elif level == 'debug':
            self.logger.debug(msg=message, exc_info=exc_info)
        elif level == 'warning':
            self.logger.warning(msg=message, exc_info=exc_info)
        elif level == 'error':
            self.logger.error(msg=message, exc_info=exc_info)
        # 这两行代码是为了避免日志输出重复问题
        self.logger.removeHandler(ch)
        self.logger.removeHandler(fh)
        fh.close()  # 关闭打开的文件

    def debug(self, msg, exc_info=None):
        self.__console('debug', msg, exc_info)

    def info(self, msg, exc_info=None):
        self.__console('info', msg, exc_info)

    def warning(self, msg, exc_info=None):
        self.__console('warning', msg, exc_info)

    def error(self, msg, exc_info=None):
        self.__console('error', msg, exc_info)


Log = Logger()
