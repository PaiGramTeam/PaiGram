from multiprocessing import RLock as Lock
from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseSettings

from utils.const import PROJECT_ROOT

__all__ = ("LoggerConfig",)


class LoggerConfig(BaseSettings):
    _lock = Lock()
    _instance: Optional["LoggerConfig"] = None

    def __new__(cls, *args, **kwargs) -> "LoggerConfig":
        with cls._lock:
            if cls._instance is None:
                cls.update_forward_refs()
                result = super(LoggerConfig, cls).__new__(cls)  # pylint: disable=E1120
                result.__init__(*args, **kwargs)
                cls._instance = result
        return cls._instance

    name: str = "logger"
    level: Optional[Union[str, int]] = None

    debug: bool = False
    width: Optional[int] = None
    keywords: List[str] = []
    time_format: str = "[%Y-%m-%d %X]"
    capture_warnings: bool = True

    log_path: Union[str, Path] = "./logs"
    project_root: Union[str, Path] = PROJECT_ROOT

    traceback_max_frames: int = 20
    traceback_locals_max_depth: Optional[int] = None
    traceback_locals_max_length: int = 10
    traceback_locals_max_string: int = 80
