import re
from functools import lru_cache
from typing import TYPE_CHECKING

from core.config import config
from utils.log._config import LoggerConfig
from utils.log._logger import LogFilter, Logger

if TYPE_CHECKING:
    from logging import LogRecord

__all__ = ["logger"]

logger = Logger(
    LoggerConfig(
        name=config.logger.name,
        width=config.logger.width,
        time_format=config.logger.time_format,
        traceback_max_frames=config.logger.traceback_max_frames,
        log_path=config.logger.path,
        keywords=config.logger.render_keywords,
        traceback_locals_max_depth=config.logger.locals_max_depth,
        traceback_locals_max_length=config.logger.locals_max_length,
        traceback_locals_max_string=config.logger_locals_max_string,
    )
)


@lru_cache
def _name_filter(record_name: str) -> bool:
    for name in config.logger.filtered_names + [config.logger.name]:
        if re.match(rf"^{name}.*?$", record_name):
            return True
    return False


def name_filter(record: "LogRecord") -> bool:
    """默认的过滤器"""
    return _name_filter(record.name)


log_filter = LogFilter()
log_filter.add_filter(name_filter)
logger.addFilter(log_filter)
