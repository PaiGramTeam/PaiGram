import logging
from logging.handlers import RotatingFileHandler
import colorlog
import os

current_path = os.path.realpath(os.getcwd())
log_path = os.path.join(current_path, "logs")
if not os.path.exists(log_path):
    os.mkdir(log_path)
log_file_name = os.path.join(log_path, "log.log")

log_colors_config = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red",
}


class Logger:
    def __init__(self):
        self.logger = logging.getLogger("TGPaimonBot")
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.CRITICAL)
        self.logger.setLevel(logging.INFO)
        self.formatter = colorlog.ColoredFormatter(
            "%(log_color)s[%(asctime)s] [%(levelname)s] - %(message)s", log_colors=log_colors_config)
        self.formatter2 = logging.Formatter("[%(asctime)s] [%(levelname)s] - %(message)s")
        fh = RotatingFileHandler(filename=log_file_name, maxBytes=1024 * 1024 * 5, backupCount=5,
                                 encoding="utf-8")
        fh.setFormatter(self.formatter2)
        root_logger.addHandler(fh)

        ch = colorlog.StreamHandler()
        ch.setFormatter(self.formatter)
        root_logger.addHandler(ch)

    def getLogger(self):
        return self.logger

    def debug(self, msg, exc_info=None):
        self.logger.debug(msg=msg, exc_info=exc_info)

    def info(self, msg, exc_info=None):
        self.logger.info(msg=msg, exc_info=exc_info)

    def warning(self, msg, exc_info=None):
        self.logger.warning(msg=msg, exc_info=exc_info)

    def error(self, msg, exc_info=None):
        self.logger.error(msg=msg, exc_info=exc_info)


Log = Logger()
