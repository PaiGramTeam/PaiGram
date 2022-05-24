import logging
from logging.handlers import RotatingFileHandler
import colorlog
import os

current_path = os.path.realpath(os.getcwd())
log_path = os.path.join(current_path, 'logs')
if not os.path.exists(log_path):
    os.mkdir(log_path)
log_file_name = os.path.join(log_path, 'log.log')

log_colors_config = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red',
}


class Logger:
    def __init__(self):
        self.logger = logging.getLogger("TGPaimonBot")
        self.logger.setLevel(logging.INFO)
        self.formatter = colorlog.ColoredFormatter(
            '%(log_color)s[%(asctime)s] [%(levelname)s] - %(message)s', log_colors=log_colors_config)
        self.formatter2 = colorlog.ColoredFormatter(
            '[%(asctime)s] [%(levelname)s] - %(message)s')

    def getLogger(self):
        return self.logger

    def _console(self, level, message, exc_info=None):
        fh = RotatingFileHandler(filename=log_file_name, maxBytes=1024 * 1024 * 5, backupCount=5,
                                 encoding='utf-8')
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

        self.logger.removeHandler(ch)
        self.logger.removeHandler(fh)
        fh.close()

    def debug(self, msg, exc_info=None):
        self._console('debug', msg, exc_info)

    def info(self, msg, exc_info=None):
        self._console('info', msg, exc_info)

    def warning(self, msg, exc_info=None):
        self._console('warning', msg, exc_info)

    def error(self, msg, exc_info=None):
        self._console('error', msg, exc_info)


Log = Logger()
