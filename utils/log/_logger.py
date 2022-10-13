import inspect
import io
import logging
import os
import sys
import traceback as traceback_
from datetime import datetime
from multiprocessing import RLock as Lock
from pathlib import Path
from types import ModuleType, TracebackType
from typing import Any, Callable, Dict, Iterable, List, Literal, Mapping, Optional, TYPE_CHECKING, Tuple, Type, Union

import ujson as json
from rich import pretty
from rich.columns import Columns
from rich.console import (
    Console,
    RenderResult,
    group,
)
from rich.highlighter import ReprHighlighter
from rich.logging import (
    LogRender as DefaultLogRender,
    RichHandler as DefaultRichHandler,
)
from rich.panel import Panel
from rich.pretty import Pretty
from rich.syntax import (
    PygmentsSyntaxTheme,
    Syntax,
)
from rich.table import Table
from rich.text import (
    Text,
    TextType,
)
from rich.theme import Theme
from rich.traceback import (
    Frame,
    Stack,
    Trace,
    Traceback as BaseTraceback,
)
from typing_extensions import Self
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
    from rich.console import (  # pylint: disable=unused-import
        ConsoleRenderable,
        RenderableType,
    )
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


def render_scope(
    scope: "Mapping[str, Any]",
    *,
    title: Optional[TextType] = None,
    sort_keys: bool = False,
    indent_guides: bool = False,
    max_length: Optional[int] = None,
    max_string: Optional[int] = None,
    max_depth: Optional[int] = None,
) -> "ConsoleRenderable":
    """在给定范围内渲染 python 变量

    Args:
        scope (Mapping): 包含变量名称和值的映射.
        title (str, optional): 标题. 默认为 None.
        sort_keys (bool, optional): 启用排序. 默认为 True.
        indent_guides (bool, optional): 启用缩进线. 默认为 False.
        max_length (int, optional): 缩写前容器的最大长度; 若为 None , 则表示没有缩写. 默认为 None.
        max_string (int, optional): 截断前字符串的最大长度; 若为 None , 则表示不会截断. 默认为 None.
        max_depth (int, optional): 嵌套数据结构的最大深度; 若为 None , 则表示会一直递归访问至最后一层. 默认为 None.

    Returns:
        ConsoleRenderable: 可被 rich 渲染的对象.
    """
    highlighter = ReprHighlighter()
    items_table = Table.grid(padding=(0, 1), expand=False)
    items_table.add_column(justify="right")

    def sort_items(item: Tuple[str, Any]) -> Tuple[bool, str]:
        # noinspection PyShadowingNames
        key, _ = item
        return not key.startswith("__"), key.lower()

    # noinspection PyTypeChecker
    items = sorted(scope.items(), key=sort_items) if sort_keys else scope.items()
    for key, value in items:
        key_text = Text.assemble(
            (key, "scope.key.special" if key.startswith("__") else "scope.key"),
            (" =", "scope.equals"),
        )
        items_table.add_row(
            key_text,
            Pretty(
                value,
                highlighter=highlighter,
                indent_guides=indent_guides,
                max_length=max_length,
                max_string=max_string,
                max_depth=max_depth,
            ),
        )
    return Panel.fit(
        items_table,
        title=title,
        border_style="scope.border",
        padding=(0, 1),
    )


class Traceback(BaseTraceback):
    locals_max_depth: Optional[int]

    def __init__(self, *args, locals_max_depth: Optional[int] = None, **kwargs):
        kwargs.update({"show_locals": True, "max_frames": config.logger.traceback_max_frames})
        super(Traceback, self).__init__(*args, **kwargs)
        self.locals_max_depth = locals_max_depth

    @classmethod
    def from_exception(
        cls,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: Optional[TracebackType],
        width: Optional[int] = 100,
        extra_lines: int = 3,
        theme: Optional[str] = None,
        word_wrap: bool = False,
        show_locals: bool = False,
        indent_guides: bool = True,
        locals_max_length: int = config.logger.locals_max_length,
        locals_max_string: int = config.logger.locals_max_string,
        locals_max_depth: Optional[int] = config.logger_locals_max_depth,
        suppress: Iterable[Union[str, ModuleType]] = (),
        max_frames: int = 100,
    ) -> "Traceback":
        rich_traceback = cls.extract(
            exc_type=exc_type,
            exc_value=exc_value,
            traceback=traceback,
            show_locals=show_locals,
            locals_max_depth=locals_max_depth,
            locals_max_string=locals_max_string,
            locals_max_length=locals_max_length,
        )
        return cls(
            rich_traceback,
            width=width,
            extra_lines=extra_lines,
            theme=PygmentsSyntaxTheme(MonokaiProStyle),
            word_wrap=word_wrap,
            show_locals=show_locals,
            indent_guides=indent_guides,
            locals_max_length=locals_max_length,
            locals_max_string=locals_max_string,
            locals_max_depth=locals_max_depth,
            suppress=suppress,
            max_frames=max_frames,
        )

    @classmethod
    def extract(
        cls,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: Optional[TracebackType],
        show_locals: bool = False,
        locals_max_length: int = 10,
        locals_max_string: int = 80,
        locals_max_depth: Optional[int] = None,
    ) -> Trace:
        # noinspection PyProtectedMember
        from rich import _IMPORT_CWD

        stacks: List[Stack] = []
        is_cause = False

        def safe_str(_object: Any) -> str:
            # noinspection PyBroadException
            try:
                return str(_object)
            except Exception:
                return "<exception str() failed>"

        while True:
            stack = Stack(
                exc_type=safe_str(exc_type.__name__),
                exc_value=safe_str(exc_value),
                is_cause=is_cause,
            )

            if isinstance(exc_value, SyntaxError):
                # noinspection PyProtectedMember
                from rich.traceback import _SyntaxError

                stack.syntax_error = _SyntaxError(
                    offset=exc_value.offset or 0,
                    filename=exc_value.filename or "?",
                    lineno=exc_value.lineno or 0,
                    line=exc_value.text or "",
                    msg=exc_value.msg,
                )

            stacks.append(stack)
            append = stack.frames.append

            for frame_summary, line_no in traceback_.walk_tb(traceback):
                filename = frame_summary.f_code.co_filename
                if filename and not filename.startswith("<"):
                    if not os.path.isabs(filename):
                        filename = os.path.join(_IMPORT_CWD, filename)
                if frame_summary.f_locals.get("_rich_traceback_omit", False):
                    continue
                frame = Frame(
                    filename=filename or "?",
                    lineno=line_no,
                    name=frame_summary.f_code.co_name,
                    locals={
                        key: pretty.traverse(
                            value,
                            max_length=locals_max_length,
                            max_string=locals_max_string,
                            max_depth=locals_max_depth,
                        )
                        for key, value in frame_summary.f_locals.items()
                    }
                    if show_locals
                    else None,
                )
                append(frame)
                if frame_summary.f_locals.get("_rich_traceback_guard", False):
                    del stack.frames[:]

            cause = getattr(exc_value, "__cause__", None)
            if cause:
                exc_type = cause.__class__
                exc_value = cause
                # __traceback__ can be None, e.g. for exceptions raised by the
                # 'multiprocessing' module
                traceback = cause.__traceback__
                is_cause = True
                continue

            cause = exc_value.__context__
            if cause and not getattr(exc_value, "__suppress_context__", False):
                exc_type = cause.__class__
                exc_value = cause
                traceback = cause.__traceback__
                is_cause = False
                continue
            # No cover, code is reached but coverage doesn't recognize it.
            break  # pragma: no cover

        trace = Trace(stacks=stacks)
        return trace

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
                yield render_scope(
                    scope=frame.locals,
                    title="locals",
                    indent_guides=self.indent_guides,
                    max_length=self.locals_max_length,
                    max_string=self.locals_max_string,
                    max_depth=self.locals_max_depth,
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
    ) -> Table:
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
    def __init__(
        self,
        *args,
        rich_tracebacks: bool = True,
        locals_max_depth: Optional[int] = config.logger.locals_max_depth,
        **kwargs,
    ) -> None:
        super(Handler, self).__init__(*args, rich_tracebacks=rich_tracebacks, **kwargs)
        self._log_render = LogRender()
        self.console = log_console
        self.tracebacks_show_locals = True
        self.keywords = self.KEYWORDS + config.logger.render_keywords
        self.locals_max_depth = locals_max_depth

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
                locals_max_depth=self.locals_max_depth,
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
