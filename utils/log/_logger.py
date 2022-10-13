import inspect
import io
import logging
import os
import traceback as traceback_
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, TYPE_CHECKING, Tuple

from typing_extensions import Self

from core.config import config
from utils.const import NOT_SET
from utils.log._handler import FileHandler, Handler
from utils.typedefs import ExceptionInfoType

if TYPE_CHECKING:
    from logging import LogRecord  # pylint: disable=unused-import

__all__ = ["logger"]

_lock = Lock()
__initialized__ = False


class Logger(logging.Logger):
    def success(
            self,
            msg: Any,
            *args: Any,
            exc_info: Optional[ExceptionInfoType] = None,
            stack_info: bool = False,
            stacklevel: int = 1,
            extra: Optional[Mapping[str, Any]] = None,
    ) -> None:
        return self.log(25, msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra)

    def exception(
            self,
            msg: Any = NOT_SET,
            *args: Any,
            exc_info: Optional[ExceptionInfoType] = True,
            stack_info: bool = False,
            stacklevel: int = 1,
            extra: Optional[Mapping[str, Any]] = None,
            **kwargs,
    ) -> None:  # pylint: disable=W1113
        super(Logger, self).exception(
            "" if msg is NOT_SET else msg,
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


class LogFilter(logging.Filter):
    _filter_list: List[Callable[["LogRecord"], bool]] = []

    def __init__(self, name: str = ""):
        super().__init__(name=name)

    def add_filter(self, f: Callable[["LogRecord"], bool]) -> Self:
        if f not in self._filter_list:
            self._filter_list.append(f)
        return self

    def filter(self, record: "LogRecord") -> bool:
        for f in self._filter_list:
            if not f(record):
                return False
        return True


def default_filter(record: "LogRecord") -> bool:
    return record.name.split(".")[0] in ["TGPaimon", "uvicorn"]


with _lock:
    if not __initialized__:
        if "PYCHARM_HOSTED" in os.environ:
            print()  # 针对 pycharm 的控制台 bug
        logging.captureWarnings(True)
        handler, debug_handler, error_handler = (
            # 控制台 log 配置
            Handler(
                locals_max_length=config.logger.locals_max_length,
                locals_max_string=config.logger.locals_max_string,
                locals_max_depth=config.logger.locals_max_depth,
            ),
            # debug.log 配置
            FileHandler(
                level=10,
                path=config.logger.path.joinpath("debug/debug.log"),
                locals_max_depth=1,
                locals_max_length=config.logger.locals_max_length,
                locals_max_string=config.logger.locals_max_string,
            ),
            # error.log 配置
            FileHandler(
                level=40,
                path=config.logger.path.joinpath("error/error.log"),
                locals_max_length=config.logger.locals_max_length,
                locals_max_string=config.logger.locals_max_string,
                locals_max_depth=config.logger.locals_max_depth,
            ),
        )

        default_log_filter = LogFilter().add_filter(default_filter)
        handler.addFilter(default_log_filter)
        debug_handler.addFilter(default_log_filter)

        level_ = 10 if config.debug else 20
        logging.basicConfig(
            level=10 if config.debug else 20,
            format="%(message)s",
            datefmt=config.logger.time_format,
            handlers=[handler, debug_handler, error_handler],
        )
        warnings_logger = logging.getLogger("py.warnings")
        warnings_logger.addHandler(handler)
        warnings_logger.addHandler(debug_handler)

        logger = Logger("TGPaimon", level_)
        logger.addHandler(handler)
        logger.addHandler(debug_handler)
        logger.addHandler(error_handler)

        __initialized__ = True
