import os
import traceback as traceback_
from types import ModuleType, TracebackType
from typing import Any, Dict, Iterable, List, Mapping, Optional, TYPE_CHECKING, Tuple, Type, Union

from rich import pretty
from rich.columns import Columns
from rich.console import RenderResult, group
from rich.highlighter import ReprHighlighter
from rich.panel import Panel
from rich.pretty import Pretty
from rich.syntax import PygmentsSyntaxTheme, Syntax
from rich.table import Table
from rich.text import Text, TextType
from rich.traceback import (
    Frame,
    LOCALS_MAX_LENGTH,
    LOCALS_MAX_STRING,
    PathHighlighter,
    Stack,
    Trace,
    Traceback as BaseTraceback,
)

from core.config import config
from utils.log._style import MonokaiProStyle

if TYPE_CHECKING:
    from rich.console import ConsoleRenderable

__all__ = ("render_scope", "Traceback")


def render_scope(
    scope: Mapping[str, Any],
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
        kwargs.update({"show_locals": True})
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
        locals_max_length: int = LOCALS_MAX_LENGTH,
        locals_max_string: int = LOCALS_MAX_STRING,
        locals_max_depth: Optional[int] = None,
        suppress: Iterable[Union[str, ModuleType]] = (),
        max_frames: int = 100,
        **kwargs,
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
        **kwargs,
    ) -> Trace:
        # noinspection PyProtectedMember
        from rich import _IMPORT_CWD

        stacks: List[Stack] = []
        is_cause = False

        def safe_str(_object: Any) -> str:
            # noinspection PyBroadException
            try:
                return str(_object)
            except Exception:  # pylint: disable=W0703
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
                if filename and not filename.startswith("<") and not os.path.isabs(filename):
                    filename = os.path.join(_IMPORT_CWD, filename)
                if frame_summary.f_locals.get("_rich_traceback_omit", False):
                    continue
                frame = Frame(
                    filename=filename or "?",
                    lineno=line_no,
                    name=frame_summary.f_code.co_name,
                    locals=(
                        {
                            key: pretty.traverse(
                                Traceback.filter_value(value),
                                max_length=locals_max_length,
                                max_string=locals_max_string,
                                max_depth=locals_max_depth,
                            )
                            for key, value in frame_summary.f_locals.items()
                        }
                        if show_locals
                        else None
                    ),
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
            break

        trace = Trace(stacks=stacks)
        return trace

    @group()
    def _render_stack(self, stack: Stack) -> RenderResult:
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

    @staticmethod
    def filter_value(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace(config.bot.token, "TOKEN")
        return value
