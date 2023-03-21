import inspect
import io
import logging
import os
import traceback as traceback_
from multiprocessing import RLock as Lock
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, List, Mapping, Optional, TYPE_CHECKING, Tuple, Type, Union

from typing_extensions import Self

from utils.log._handler import FileHandler, Handler
from utils.typedefs import LogFilterType

if TYPE_CHECKING:
    from logging import LogRecord

    from utils.log._config import LoggerConfig

__all__ = ("Logger", "LogFilter")

SysExcInfoType = Union[
    Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
    Tuple[None, None, None],
]
ExceptionInfoType = Union[bool, SysExcInfoType, BaseException]

_lock = Lock()
NONE = object()


class Logger(logging.Logger):  # skipcq: PY-A6006
    _instance: Optional["Logger"] = None

    def __new__(cls, *args, **kwargs) -> "Logger":
        with _lock:
            if cls._instance is None:
                result = super(Logger, cls).__new__(cls)
                cls._instance = result
        return cls._instance

    def __init__(self, config: "LoggerConfig" = None) -> None:
        from utils.log._config import LoggerConfig

        self.config = config or LoggerConfig()

        level_ = 10 if self.config.debug else 20
        super().__init__(
            name=self.config.name,
            level=level_ if self.config.level is None else self.config.level,
        )

        log_path = Path(self.config.project_root).joinpath(self.config.log_path)
        handler_config = {
            "width": self.config.width,
            "keywords": self.config.keywords,
            "locals_max_length": self.config.traceback_locals_max_length,
            "locals_max_string": self.config.traceback_locals_max_string,
            "project_root": self.config.project_root,
            "log_time_format": self.config.time_format,
        }
        handler, debug_handler, error_handler = (
            # 控制台 log 配置
            Handler(color_system=self.config.color_system, **handler_config),
            # debug.log 配置
            FileHandler(level=10, path=log_path.joinpath("debug/debug.log"), locals_max_depth=1, **handler_config),
            # error.log 配置
            FileHandler(
                level=40,
                path=log_path.joinpath("error/error.log"),
                locals_max_depth=self.config.traceback_locals_max_depth,
                **handler_config,
            ),
        )
        logging.basicConfig(
            level=10 if self.config.debug else 20,
            format="%(message)s",
            datefmt=self.config.time_format,
            handlers=[handler, debug_handler, error_handler],
        )
        if self.config.capture_warnings:
            logging.captureWarnings(True)
            warnings_logger = logging.getLogger("py.warnings")
            warnings_logger.addHandler(handler)
            warnings_logger.addHandler(debug_handler)

        self.addHandler(handler)
        self.addHandler(debug_handler)
        self.addHandler(error_handler)

    def success(
        self,
        msg: Any,
        *args: Any,
        exc_info: Optional[ExceptionInfoType] = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> None:
        return self.log(
            25,
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def exception(  # pylint: disable=W1113
        self,
        msg: Any = NONE,
        *args: Any,
        exc_info: Optional[ExceptionInfoType] = True,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> None:
        super(Logger, self).exception(
            "" if msg is NONE else msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
        )

    def findCaller(self, stack_info: bool = False, stacklevel: int = 1) -> Tuple[str, int, str, Optional[str]]:
        frame = inspect.currentframe()
        if frame is not None:
            frame = frame.f_back
        original_frame = frame
        while frame and stacklevel > 1:
            frame = frame.f_back
            stacklevel -= 1
        if not frame:
            frame = original_frame
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(frame, "f_code"):
            code = frame.f_code
            filename = os.path.normcase(code.co_filename)
            if filename in [
                os.path.normcase(Path(__file__).resolve()),
                os.path.normcase(logging.addLevelName.__code__.co_filename),
            ]:
                frame = frame.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write("Stack (most recent call last):\n")
                traceback_.print_stack(frame, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == "\n":
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (code.co_filename, frame.f_lineno, code.co_name, sinfo)
            break
        return rv

    def addFilter(self, log_filter: LogFilterType) -> None:  # pylint: disable=arguments-differ
        for handler in self.handlers:
            handler.addFilter(log_filter)


class LogFilter(logging.Filter):  # skipcq: PY-A6006
    _filter_list: List[Callable[["LogRecord"], bool]] = []

    def __init__(self, name: str = ""):
        super().__init__(name=name)

    def add_filter(self, f: Callable[["LogRecord"], bool]) -> Self:
        if f not in self._filter_list:
            self._filter_list.append(f)
        return self

    def filter(self, record: "LogRecord") -> bool:
        return all(map(lambda func: func(record), self._filter_list))
