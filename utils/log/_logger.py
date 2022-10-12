import inspect
import io
import logging
import os
import sys
import traceback as traceback_
from datetime import datetime
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Literal, Mapping, Optional, TYPE_CHECKING, Tuple, Union

import ujson as json
from rich.columns import Columns
from rich.console import (
    Console,
    RenderResult,
    group,
)
from rich.logging import (
    LogRender as DefaultLogRender,
    RichHandler as DefaultRichHandler,
)
from rich.syntax import (
    PygmentsSyntaxTheme,
    Syntax,
)
from rich.text import (
    Text,
    TextType,
)
from rich.theme import Theme
from rich.traceback import (
    Stack,
    Traceback as BaseTraceback,
)
from ujson import JSONDecodeError

from core.config import config
from utils.const import NOT_SET, PROJECT_ROOT
from utils.log._file import FileIO
from utils.log._style import (
    DEFAULT_STYLE,
    MonokaiProStyle,
)
from utils.typedefs import ExceptionInfoType

if TYPE_CHECKING:
    from rich.table import Table  # pylint: disable=unused-import
    from rich.console import (  # pylint: disable=unused-import
        ConsoleRenderable,
        RenderableType,
    )
    from rich.console import (  # pylint: disable=unused-import
        ConsoleRenderable,
        RenderableType,
    )
    from rich.table import Table  # pylint: disable=unused-import
    from logging import LogRecord  # pylint: disable=unused-import

__all__ = ["logger"]

_lock = Lock()
__initialized__ = False

FormatTimeCallable = Callable[[datetime], Text]

logging.addLevelName(5, "TRACE")
logging.addLevelName(25, "SUCCESS")
color_system: Literal["windows", "truecolor"]
if sys.platform == "win32":
    color_system = "windows"
else:
    color_system = "truecolor"
# noinspection SpellCheckingInspection
log_console = Console(color_system=color_system, theme=Theme(DEFAULT_STYLE), width=config.logger.width)


class Traceback(BaseTraceback):
    def __init__(self, *args, **kwargs):
        kwargs.update(
            {
                "show_locals": True,
                "max_frames": config.logger.traceback_max_frames,
                "locals_max_length": 3,
                "locals_max_string": 80,
            }
        )
        super(Traceback, self).__init__(*args, **kwargs)
        self.theme = PygmentsSyntaxTheme(MonokaiProStyle)

    @group()
    def _render_stack(self, stack: Stack) -> RenderResult:
        from rich.traceback import (
            PathHighlighter,
            Frame,
        )

        path_highlighter = PathHighlighter()
        theme = self.theme
        code_cache: Dict[str, str] = {}

        # noinspection PyShadowingNames
        def read_code(filename: str) -> str:
            code = code_cache.get(filename)
            if code is None:
                with open(filename, "rt", encoding="utf-8", errors="replace") as code_file:
                    code = code_file.read()
                code_cache[filename] = code
            return code

        # noinspection PyShadowingNames
        def render_locals(frame: Frame) -> Iterable["ConsoleRenderable"]:
            if frame.locals:
                from rich.scope import render_scope

                yield render_scope(
                    frame.locals,
                    title="locals",
                    indent_guides=self.indent_guides,
                    max_length=self.locals_max_length,
                    max_string=self.locals_max_string,
                )

        exclude_frames: Optional[range] = None
        if self.max_frames != 0:
            exclude_frames = range(
                self.max_frames // 2,
                len(stack.frames) - self.max_frames // 2,
            )

        excluded = False
        for frame_index, frame in enumerate(stack.frames):

            if exclude_frames and frame_index in exclude_frames:
                excluded = True
                continue

            if excluded:
                if exclude_frames is None:
                    raise ValueError(exclude_frames)
                yield Text(
                    f"\n... {len(exclude_frames)} frames hidden ...",
                    justify="center",
                    style="traceback.error",
                )
                excluded = False

            first = frame_index == 0
            frame_filename = frame.filename
            suppressed = any(frame_filename.startswith(path) for path in self.suppress)

            text = Text.assemble(
                path_highlighter(Text(frame.filename, style="pygments.string")),
                (":", "pygments.text"),
                (str(frame.lineno), "pygments.number"),
                " in ",
                (frame.name, "pygments.function"),
                style="pygments.text",
            )
            if not frame.filename.startswith("<") and not first:
                yield ""
            yield text
            if frame.filename.startswith("<"):
                yield from render_locals(frame)
                continue
            if not suppressed:
                try:
                    if self.width is not None:
                        code_width = self.width - 5
                    else:
                        code_width = 100
                    code = read_code(frame.filename)
                    lexer_name = self._guess_lexer(frame.filename, code)
                    syntax = Syntax(
                        code,
                        lexer_name,
                        theme=theme,
                        line_numbers=True,
                        line_range=(
                            frame.lineno - self.extra_lines,
                            frame.lineno + self.extra_lines,
                        ),
                        highlight_lines={frame.lineno},
                        word_wrap=self.word_wrap,
                        code_width=code_width,
                        indent_guides=self.indent_guides,
                        dedent=False,
                    )
                    yield ""
                except Exception as error:  # pylint: disable=W0703
                    yield Text.assemble(
                        (f"\n{error}", "traceback.error"),
                    )
                else:
                    yield (
                        Columns(
                            [
                                syntax,
                                *render_locals(frame),
                            ],
                            padding=1,
                        )
                        if frame.locals
                        else syntax
                    )


class LogRender(DefaultLogRender):
    @property
    def last_time(self):
        return self._last_time

    @last_time.setter
    def last_time(self, last_time):
        self._last_time = last_time

    def __init__(self, *args, **kwargs):
        super(LogRender, self).__init__(*args, **kwargs)
        self.show_level = True
        self.time_format = config.logger.time_format

    def __call__(
        self,
        console: "Console",
        renderables: Iterable["ConsoleRenderable"],
        log_time: Optional[datetime] = None,
        time_format: Optional[Union[str, FormatTimeCallable]] = None,
        level: TextType = "",
        path: Optional[str] = None,
        line_no: Optional[int] = None,
        link_path: Optional[str] = None,
    ) -> "Table":
        from rich.containers import Renderables
        from rich.table import Table

        output = Table.grid(padding=(0, 1))
        output.expand = True
        output.add_column(style="log.time")
        output.add_column(style="log.level", width=self.level_width)
        output.add_column(ratio=1, style="log.message", overflow="fold")
        if path:
            output.add_column(style="log.path")
        if line_no:
            output.add_column(style="log.line_no", width=4)
        row: List["RenderableType"] = []
        if self.show_time:
            log_time = log_time or log_console.get_datetime()
            time_format = time_format or self.time_format
            if callable(time_format):
                log_time_display = time_format(log_time)
            else:
                log_time_display = Text(log_time.strftime(time_format))
            if log_time_display == self.last_time and self.omit_repeated_times:
                row.append(Text(" " * len(log_time_display)))
            else:
                row.append(log_time_display)
                self.last_time = log_time_display
        if self.show_level:
            row.append(level)

        row.append(Renderables(renderables))
        if path:
            path_text = Text()
            path_text.append(path, style=f"link file://{link_path}" if link_path else "")
            row.append(path_text)

        line_no_text = Text()
        line_no_text.append(str(line_no), style=f"link file://{link_path}#{line_no}" if link_path else "")
        row.append(line_no_text)

        output.add_row(*row)
        return output


class Handler(DefaultRichHandler):
    def __init__(self, *args, **kwargs):
        super(Handler, self).__init__(*args, **kwargs)
        self._log_render = LogRender()
        self.console = log_console
        self.rich_tracebacks = True
        self.tracebacks_show_locals = True
        self.keywords = self.KEYWORDS + config.logger.render_keywords

    def render(
        self,
        *,
        record: "LogRecord",
        traceback: Optional[Traceback],
        message_renderable: Optional["ConsoleRenderable"],
    ) -> "ConsoleRenderable":
        if record.pathname != "<input>":
            try:
                path = str(Path(record.pathname).relative_to(PROJECT_ROOT))
                path = path.split(".")[0].replace(os.sep, ".")
            except ValueError:
                import site

                path = None
                for s in site.getsitepackages():
                    try:
                        path = str(Path(record.pathname).relative_to(Path(s)))
                        break
                    except ValueError:
                        continue
                if path is None:
                    path = "<SITE>"
                else:
                    path = path.split(".")[0].replace(os.sep, ".")
        else:
            path = "<INPUT>"
        path = path.replace("lib.site-packages.", "")
        _level = self.get_level_text(record)
        time_format = None if self.formatter is None else self.formatter.datefmt
        log_time = datetime.fromtimestamp(record.created)

        log_renderable = self._log_render(
            self.console,
            (
                [message_renderable]
                if not traceback
                else ([message_renderable, traceback] if message_renderable is not None else [traceback])
            ),
            log_time=log_time,
            time_format=time_format,
            level=_level,
            path=path,
            link_path=record.pathname if self.enable_link_path else None,
            line_no=record.lineno,
        )
        return log_renderable

    def render_message(self, record: "LogRecord", message: Any) -> "ConsoleRenderable":
        use_markup = getattr(record, "markup", self.markup)
        if isinstance(message, str):
            message_text = Text.from_markup(message) if use_markup else Text(message)
            highlighter = getattr(record, "highlighter", self.highlighter)
        else:
            from rich.highlighter import JSONHighlighter
            from rich.json import JSON

            highlighter = JSONHighlighter()
            message_text = JSON.from_data(message, indent=4).text

        if highlighter is not None:
            # noinspection PyCallingNonCallable
            message_text = highlighter(message_text)

        if self.keywords is None:
            self.keywords = self.KEYWORDS

        if self.keywords:
            message_text.highlight_words(self.keywords, "logging.keyword")

        return message_text

    def emit(self, record: "LogRecord") -> None:
        message = self.format(record)
        _traceback = None
        if self.rich_tracebacks and record.exc_info and record.exc_info != (None, None, None):
            exc_type, exc_value, exc_traceback = record.exc_info
            if exc_type is None or exc_value is None:
                raise ValueError(record)
            _traceback = Traceback.from_exception(
                exc_type,
                exc_value,
                exc_traceback,
                width=self.tracebacks_width,
                extra_lines=self.tracebacks_extra_lines,
                word_wrap=self.tracebacks_word_wrap,
                show_locals=self.tracebacks_show_locals,
                locals_max_length=self.locals_max_length,
                locals_max_string=self.locals_max_string,
                suppress=self.tracebacks_suppress,
            )
            message = record.getMessage()
            if self.formatter:
                record.message = record.getMessage()
                formatter = self.formatter
                if hasattr(formatter, "usesTime") and formatter.usesTime():
                    record.asctime = formatter.formatTime(record, formatter.datefmt)
                message = formatter.formatMessage(record)
            if message == str(exc_value):
                message = None

        if message is not None:
            try:
                message_renderable = self.render_message(record, json.loads(message))
            except JSONDecodeError:
                message_renderable = self.render_message(record, message)
        else:
            message_renderable = None
        log_renderable = self.render(record=record, traceback=_traceback, message_renderable=message_renderable)
        # noinspection PyBroadException
        try:
            self.console.print(log_renderable)
        except Exception:  # pylint: disable=W0703
            self.handleError(record)


class FileHandler(Handler):
    def __init__(self, *args, path: Path, **kwargs):
        super().__init__(*args, **kwargs)
        while True:
            try:
                path.parent.mkdir(exist_ok=True)
                break
            except FileNotFoundError:
                parent = path.parent
                while True:
                    try:
                        parent.mkdir(exist_ok=True)
                        break
                    except FileNotFoundError:
                        parent = parent.parent
        path.parent.mkdir(exist_ok=True)
        self.console = Console(width=180, file=FileIO(path), theme=Theme(DEFAULT_STYLE))


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


with _lock:
    if not __initialized__:
        if "PYCHARM_HOSTED" in os.environ:
            print()  # 针对 pycharm 的控制台 bug
        logging.captureWarnings(True)
        handler, debug_handler, error_handler = (
            Handler(locals_max_length=4),
            FileHandler(level=10, path=config.logger.path.joinpath("debug/debug.log")),
            FileHandler(level=40, path=config.logger.path.joinpath("error/error.log")),
        )

        log_filter = logging.Filter("TGPaimon")
        handler.addFilter(log_filter)
        debug_handler.addFilter(log_filter)

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
