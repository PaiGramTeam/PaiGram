from typing import TYPE_CHECKING

from core.config import config
from utils.const import PROJECT_ROOT
from utils.log._config import LoggerConfig
from utils.log._logger import LogFilter, Logger

if TYPE_CHECKING:
    from logging import LogRecord

__all__ = ["logger"]

logger = Logger(
    LoggerConfig(
        name="TGPaimon",
        width=config.logger.width,
        time_format=config.logger.time_format,
        traceback_max_frames=config.logger.traceback_max_frames,
        log_path=config.logger.path,
        keywords=config.logger.render_keywords,
        traceback_locals_max_depth=config.logger.locals_max_depth,
        traceback_locals_max_length=config.logger.locals_max_length,
        traceback_locals_max_string=config.logger_locals_max_string,
        project_root=PROJECT_ROOT,
    )
)


def default_filter(record: "LogRecord") -> bool:
    """默认的过滤器"""
    return record.name.split(".")[0] in ["TGPaimon", "uvicorn"]


default_log_filter = LogFilter().add_filter(default_filter)
logger.addFilter(default_log_filter)
