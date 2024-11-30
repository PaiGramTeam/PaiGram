from multiprocessing import RLock as Lock
from pathlib import Path
from typing import List, Literal, Optional, Union, ClassVar

from pydantic_settings import BaseSettings

from utils.const import PROJECT_ROOT

__all__ = ("LoggerConfig",)


class LoggerConfig(BaseSettings):
    _lock: ClassVar[Lock] = Lock()
    _instance: ClassVar[Optional["LoggerConfig"]] = None

    def __new__(cls, *args, **kwargs) -> "LoggerConfig":
        with cls._lock:
            if cls._instance is None:
                cls.model_rebuild()
                result = super(LoggerConfig, cls).__new__(cls)  # pylint: disable=E1120
                result.__init__(*args, **kwargs)
                cls._instance = result
        return cls._instance

    name: str = "PaiGram-logger"
    """logger 名称"""
    level: Optional[Union[str, int]] = None
    """logger 的 level"""

    debug: bool = False
    """是否 debug"""
    width: Optional[int] = None
    """输出时的宽度"""
    keywords: List[str] = []
    """高亮的关键字"""
    time_format: str = "[%Y-%m-%d %X]"
    """时间格式"""
    capture_warnings: bool = True
    """是否捕获 warning"""
    color_system: Literal["auto", "standard", "256", "truecolor", "windows"] = "auto"
    """颜色模式： 自动、标准、256色、真彩、Windows模式"""

    log_path: Union[str, Path] = "./logs"
    """log 所保存的路径，项目根目录的相对路径"""
    project_root: Union[str, Path] = PROJECT_ROOT
    """项目根目录"""

    traceback_max_frames: int = 20
    traceback_locals_max_depth: Optional[int] = None
    traceback_locals_max_length: int = 10
    traceback_locals_max_string: int = 80
