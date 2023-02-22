import re
from functools import lru_cache
from typing import TYPE_CHECKING

from core.config import config
from utils.log._config import LoggerConfig
from utils.log._logger import LogFilter, Logger

if TYPE_CHECKING:
    from logging import LogRecord

__all__ = ("logger",)

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
        traceback_locals_max_string=config.logger.locals_max_string,
    )
)


@lru_cache
def _whitelist_name_filter(record_name: str) -> bool:
    """白名单过滤器"""
    return any(re.match(rf"^{name}.*?$", record_name) for name in config.logger.filtered_names + [config.logger.name])


def name_filter(record: "LogRecord") -> bool:
    """默认的过滤器. 白名单

    根据当前的 record 的 name 判断是否需要打印。如果应该打印，则返回 True;否则返回 False。
    """
    return _whitelist_name_filter(record.name)


log_filter = LogFilter()
log_filter.add_filter(name_filter)
logger.addFilter(log_filter)
