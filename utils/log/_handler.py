import logging
import os
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Literal,
    Optional,
    TYPE_CHECKING,
    Union,
)

from rich.console import Console
from rich.logging import LogRender as DefaultLogRender, RichHandler as DefaultRichHandler
from rich.table import Table
from rich.text import Text, TextType
from rich.theme import Theme

from utils.log._file import FileIO
from utils.log._style import DEFAULT_STYLE
from utils.log._traceback import Traceback

try:
    import ujson as jsonlib
    from ujson import JSONDecodeError
except ImportError:
    import json as jsonlib
    from json import JSONDecodeError

if TYPE_CHECKING:
    from rich.console import (
        ConsoleRenderable,
        RenderableType,
    )
    from logging import LogRecord

__all__ = ["LogRender", "Handler", "FileHandler"]

FormatTimeCallable = Callable[[datetime], Text]

logging.addLevelName(5, "TRACE")
logging.addLevelName(25, "SUCCESS")


class LogRender(DefaultLogRender):
    @property
    def last_time(self):
        """上次打印的时间"""
        return self._last_time

    @last_time.setter
    def last_time(self, last_time):
        self._last_time = last_time

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
            log_time = log_time or console.get_datetime()
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
        line_no_text.append(
            str(line_no),
            style=f"link file://{link_path}#{line_no}" if link_path else "",
        )
        row.append(line_no_text)

        output.add_row(*row)
        return output


class Handler(DefaultRichHandler):
    def __init__(
        self,
        *args,
        width: int = None,
        rich_tracebacks: bool = True,
        locals_max_depth: Optional[int] = None,
        tracebacks_max_frames: int = 100,
        keywords: Optional[List[str]] = None,
        log_time_format: Union[str, FormatTimeCallable] = "[%x %X]",
        color_system: Literal["auto", "standard", "256", "truecolor", "windows"] = "auto",
        project_root: Union[str, Path] = os.getcwd(),
        auto_load_json: bool = False,
        **kwargs,
    ) -> None:
        super(Handler, self).__init__(*args, rich_tracebacks=rich_tracebacks, **kwargs)
        self._log_render = LogRender(time_format=log_time_format, show_level=True)
        self.console = Console(color_system=color_system, theme=Theme(DEFAULT_STYLE), width=width)
        self.tracebacks_show_locals = True
        self.tracebacks_max_frames = tracebacks_max_frames
        self.render_keywords = self.KEYWORDS + (keywords or [])
        self.locals_max_depth = locals_max_depth
        self.project_root = project_root
        self.auto_load_json = auto_load_json

    def render(
        self,
        *,
        record: "LogRecord",
        traceback: Optional[Traceback],
        message_renderable: Optional["ConsoleRenderable"],
    ) -> "ConsoleRenderable":
        if record.pathname != "<input>":
            try:
                path = str(Path(record.pathname).relative_to(self.project_root))
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

        if not traceback:
            renderables = [message_renderable]
        else:
            renderables = [message_renderable, traceback] if message_renderable is not None else [traceback]

        log_renderable = self._log_render(
            self.console,
            renderables,
            log_time=log_time,
            time_format=time_format,
            level=_level,
            path=path,
            link_path=record.pathname if self.enable_link_path else None,
            line_no=record.lineno,
        )
        return log_renderable

    def render_message(
        self,
        record: "LogRecord",
        message: Any,
    ) -> "ConsoleRenderable":
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

        if self.render_keywords is None:
            self.render_keywords = self.KEYWORDS

        if self.render_keywords:
            message_text.highlight_words(self.render_keywords, "logging.keyword")

        return message_text

    def emit(self, record: "LogRecord") -> None:
        message = self.format(record)
        _traceback = None
        if self.rich_tracebacks and record.exc_info and record.exc_info != (None, None, None):
            exc_type, exc_value, exc_traceback = record.exc_info
            if exc_type is None or exc_value is None:
                raise ValueError(record)
            try:
                _traceback = Traceback.from_exception(
                    exc_type,
                    exc_value,
                    exc_traceback,
                    width=self.tracebacks_width,
                    extra_lines=self.tracebacks_extra_lines,
                    word_wrap=self.tracebacks_word_wrap,
                    show_locals=(getattr(record, "show_locals", None) or self.tracebacks_show_locals),
                    locals_max_length=(getattr(record, "locals_max_length", None) or self.locals_max_length),
                    locals_max_string=(getattr(record, "locals_max_string", None) or self.locals_max_string),
                    locals_max_depth=getattr(record, "locals_max_depth", self.locals_max_depth),
                    suppress=self.tracebacks_suppress,
                    max_frames=self.tracebacks_max_frames,
                )
            except ImportError:
                return
            message = record.getMessage()
            if self.formatter:
                record.message = record.getMessage()
                formatter = self.formatter
                if hasattr(formatter, "usesTime") and formatter.usesTime():
                    record.asctime = formatter.formatTime(record, formatter.datefmt)
                message = formatter.formatMessage(record)
            if message == str(exc_value):
                message = None

        message_renderable = None
        if message is not None:
            try:
                if self.auto_load_json:
                    message_renderable = self.render_message(record, jsonlib.loads(message))
            except JSONDecodeError:
                pass
            finally:
                message_renderable = message_renderable or self.render_message(record, message)
        log_renderable = self.render(record=record, traceback=_traceback, message_renderable=message_renderable)
        # noinspection PyBroadException
        try:
            self.console.print(log_renderable)
        except Exception:  # pylint: disable=W0703
            self.handleError(record)


class FileHandler(Handler):
    def __init__(
        self,
        *args,
        width: int = None,
        path: Path,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        path.parent.mkdir(exist_ok=True, parents=True)
        self.console = Console(width=width, file=FileIO(path), theme=Theme(DEFAULT_STYLE))
