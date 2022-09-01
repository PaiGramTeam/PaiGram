import logging
import os
from datetime import datetime
from multiprocessing import RLock as Lock
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict, Iterable,
    List, Optional,
    TYPE_CHECKING,
    Union,
)

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

from utils.log._style import (
    DEFAULT_STYLE,
    MonokaiProStyle,
)

if TYPE_CHECKING:
    from rich.table import Table
    from rich.text import TextType
    from rich.console import (
        ConsoleRenderable,
        RenderableType,
    )
    from rich.console import (
        ConsoleRenderable,
        RenderableType,
    )
    from rich.table import Table
    from logging import LogRecord

__all__ = ["logger"]

_lock = Lock()
__initialized__ = False

FormatTimeCallable = Callable[[datetime], Text]

logging.addLevelName(5, 'TRACE')
logging.addLevelName(22, 'PLUGIN')
logging.addLevelName(25, 'SUCCESS')
# noinspection SpellCheckingInspection
log_console = Console(
    color_system='windows', theme=Theme(DEFAULT_STYLE),
    width=180 if os.environ.get("PYTHONUNBUFFERED", None) else None
)


class Traceback(BaseTraceback):
    def __init__(self, *args, **kwargs):
        kwargs.update({
            'show_locals': True,
            'max_frames': 20
        })
        super(Traceback, self).__init__(*args, **kwargs)
        self.theme = PygmentsSyntaxTheme(MonokaiProStyle)
        # if log_console.width >= 150:
        #     self.width = 150

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
                with open(
                        filename, "rt", encoding="utf-8", errors="replace"
                ) as code_file:
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
                assert exclude_frames is not None
                yield Text(
                    f"\n... {len(exclude_frames)} frames hidden ...",
                    justify="center",
                    style="traceback.error",
                )
                excluded = False

            first = frame_index == 0
            frame_filename = frame.filename
            suppressed = any(
                frame_filename.startswith(path) for path in self.suppress)

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
                except Exception as error:
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
    def __init__(self, *args, **kwargs):
        super(LogRender, self).__init__(*args, **kwargs)
        self.show_level = True
        self.time_format = "[%Y-%m-%d %X]"

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
            output.add_column(style='log.line_no', width=4)
        row: List["RenderableType"] = []
        if self.show_time:
            log_time = log_time or log_console.get_datetime()
            time_format = time_format or self.time_format
            if callable(time_format):
                log_time_display = time_format(log_time)
            else:
                log_time_display = Text(log_time.strftime(time_format))
            if log_time_display == self._last_time and self.omit_repeated_times:
                row.append(Text(" " * len(log_time_display)))
            else:
                row.append(log_time_display)
                self._last_time = log_time_display
        if self.show_level:
            row.append(level)

        row.append(Renderables(renderables))
        if path:
            path_text = Text()
            path_text.append(path)
            row.append(path_text)

        row.append(str(line_no))

        output.add_row(*row)
        return output


class Handler(DefaultRichHandler):
    def __init__(self, *args, **kwargs):
        super(Handler, self).__init__(*args, **kwargs)
        self._log_render = LogRender()
        self.console = log_console
        self.rich_tracebacks = True
        self.tracebacks_show_locals = True
        self.markup = True

    def render(
            self,
            *,
            record: "LogRecord",
            traceback: Optional[Traceback],
            message_renderable: Optional["ConsoleRenderable"],
    ) -> "ConsoleRenderable":
        if record.pathname != '<input>':
            try:
                path = str(Path(record.pathname).relative_to(PROJECT_ROOT))
                path = path.split('.')[0].replace('\\', '.').replace('/', '.')
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
                    path = path.split('.')[0].replace('\\', '.').replace('/',
                                                                         '.')
        else:
            path = '<INPUT>'
        path = path.replace('lib.site-packages.', '')
        level = self.get_level_text(record)
        time_format = None if self.formatter is None else self.formatter.datefmt
        log_time = datetime.fromtimestamp(record.created)

        log_renderable = self._log_render(
            self.console,
            (
                [message_renderable]
                if not traceback else
                (
                    [message_renderable, traceback]
                    if message_renderable is not None else
                    [traceback]
                )
            ),
            log_time=log_time,
            time_format=time_format,
            level=level,
            path=path,
            line_no=record.lineno,
            # link_path=record.pathname if self.enable_link_path else None,
        )
        return log_renderable

    def render_message(
            self, record: "LogRecord", message: Any
    ) -> "ConsoleRenderable":
        use_markup = getattr(record, "markup", self.markup)
        if isinstance(message, str):
            message_text = (
                Text.from_markup(message) if use_markup else Text(message)
            )
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

    def handle(self, record: "LogRecord") -> None:
        message = self.format(record)
        traceback = None
        if (
                self.rich_tracebacks
                and record.exc_info
                and record.exc_info != (None, None, None)
        ):
            exc_type, exc_value, exc_traceback = record.exc_info
            assert exc_type is not None
            assert exc_value is not None
            try:
                traceback = Traceback.from_exception(
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
            except ImportError:
                return
            except Exception as e:
                print(type(e), e)
                return
            message = record.msg.split('\n')[0]
            if self.formatter:
                record.message = record.getMessage()
                formatter = self.formatter
                if hasattr(formatter, "usesTime") and formatter.usesTime():
                    record.asctime = formatter.formatTime(
                        record, formatter.datefmt
                    )
                message = formatter.formatMessage(record)
            if message == str(exc_value):
                message = None

        # noinspection PyBroadException
        try:
            message = json.loads(message)
        except Exception:
            pass

        if message is not None:
            message_renderable = self.render_message(record, message)
        else:
            message_renderable = None
        log_renderable = self.render(
            record=record, traceback=traceback,
            message_renderable=message_renderable
        )
        # noinspection PyBroadException
        try:
            self.console.print(log_renderable)
        except Exception:
            self.handleError(record)


with _lock:
    if not __initialized__:
        import os
        from loguru import logger
        from core.config import AppConfig
        from utils.const import PROJECT_ROOT

        # noinspection SpellCheckingInspection
        if os.environ.get('PYTHONUNBUFFERED', 0):
            print()

        logging.basicConfig(
            level=10 if AppConfig().debug else 20,
            format="%(message)s",
            datefmt="[%Y-%m-%d %X]",
            handlers=[Handler()]
        )

        # noinspection PyUnresolvedReferences,PyProtectedMember
        for key, value in logging._nameToLevel.items():
            # noinspection PyUnresolvedReferences,PyProtectedMember
            if key not in logger._core.levels.keys():
                logger.level(key, value)

        logger.remove()
        logger.add(Handler(), format="{message}", colorize=False, enqueue=True)
        logger.add(
            PROJECT_ROOT / 'log/errors.log',
            rotation="00:00",
            diagnose=False,
            level="ERROR",
            colorize=False,
            format="<g>{time:YYYY-MM-DD}</g> <m>{time:HH:mm:ss.SSSS}</m> "
                   "<level>{level.icon}</level> [<level>{level}</level>] "
                   "<w>[</w><c><u>{name}</u></c><w>]</w> "
                   "{message}"
        )
        __initialized__ = True
