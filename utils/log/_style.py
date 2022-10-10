from typing import Dict

from pygments.style import Style as PyStyle
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
)
from rich.style import Style

__all__ = [
    "MonokaiProStyle",
    "DEFAULT_STYLE",
    "BACKGROUND",
    "FOREGROUND",
    "BLACK",
    "DARK_GREY",
    "LIGHT_GREY",
    "GREY",
    "RED",
    "MAGENTA",
    "GREEN",
    "YELLOW",
    "ORANGE",
    "PURPLE",
    "BLUE",
    "CYAN",
    "WHITE",
]

BACKGROUND = "#272822"
FOREGROUND = "#f8f8f2"

BLACK = "#1A1A1A"
DARK_GREY = "#363537"
LIGHT_GREY = "#69676c"
GREY = "#595959"
RED = "#ff6188"
MAGENTA = "#FC61D3"
GREEN = "#7bd88f"
YELLOW = "#ffd866"
ORANGE = "#fc9867"
PURPLE = "#ab9df2"
BLUE = "#81a1c1"
CYAN = "#78dce8"
WHITE = "#e5e9f0"


class MonokaiProStyle(PyStyle):
    background_color = DARK_GREY
    highlight_color = "#49483e"

    styles = {
        # No corresponding class for the following:
        Text: WHITE,  # class:  ''
        Error: "#fc618d bg:#1e0010",  # class: 'err'
        Comment: LIGHT_GREY,  # class: 'c'
        Comment.Multiline: YELLOW,  # class: 'cm'
        Keyword: RED,  # class: 'k'
        Keyword.Namespace: GREEN,  # class: 'kn'
        Operator: RED,  # class: 'o'
        Punctuation: WHITE,  # class: 'p'
        Name: WHITE,  # class: 'n'
        Name.Attribute: GREEN,  # class: 'na' - to be revised
        Name.Builtin: CYAN,  # class: 'nb'
        Name.Builtin.Pseudo: ORANGE,  # class: 'bp'
        Name.Class: GREEN,  # class: 'nc' - to be revised
        Name.Decorator: PURPLE,  # class: 'nd' - to be revised
        Name.Exception: GREEN,  # class: 'ne'
        Name.Function: GREEN,  # class: 'nf'
        Name.Property: ORANGE,  # class: 'py'
        Number: PURPLE,  # class: 'm'
        Literal: PURPLE,  # class: 'l'
        Literal.Date: ORANGE,  # class: 'ld'
        String: YELLOW,  # class: 's'
        String.Regex: ORANGE,  # class: 'sr'
        Generic.Deleted: YELLOW,  # class: 'gd',
        Generic.Emph: "italic",  # class: 'ge'
        Generic.Inserted: GREEN,  # class: 'gi'
        Generic.Strong: "bold",  # class: 'gs'
        Generic.Subheading: LIGHT_GREY,  # class: 'gu'
    }


DEFAULT_STYLE: Dict[str, Style] = {
    # base
    "none": Style.null(),
    "reset": Style(
        color=FOREGROUND,
        bgcolor=BACKGROUND,
        dim=False,
        bold=False,
        italic=False,
        underline=False,
        blink=False,
        blink2=False,
        reverse=False,
        conceal=False,
        strike=False,
    ),
    "dim": Style(dim=True),
    "bright": Style(dim=False),
    "bold": Style(bold=True),
    "strong": Style(bold=True),
    "code": Style(reverse=True, bold=True),
    "italic": Style(italic=True),
    "emphasize": Style(italic=True),
    "underline": Style(underline=True),
    "blink": Style(blink=True),
    "blink2": Style(blink2=True),
    "reverse": Style(reverse=True),
    "strike": Style(strike=True),
    "black": Style(color=BLACK),
    "red": Style(color=RED),
    "green": Style(color=GREEN),
    "yellow": Style(color=YELLOW),
    "magenta": Style(color=MAGENTA),
    "blue": Style(color=BLUE),
    "cyan": Style(color=CYAN),
    "white": Style(color=WHITE),
    # inspect
    "inspect.attr": Style(color=YELLOW, italic=True),
    "inspect.attr.dunder": Style(color=YELLOW, italic=True, dim=True),
    "inspect.callable": Style(bold=True, color=RED),
    "inspect.def": Style(italic=True, color="bright_cyan"),
    "inspect.class": Style(italic=True, color="bright_cyan"),
    "inspect.error": Style(bold=True, color=RED),
    "inspect.equals": Style(),
    "inspect.help": Style(color=CYAN),
    "inspect.doc": Style(dim=True),
    "inspect.value.border": Style(color=GREEN),
    # live
    "live.ellipsis": Style(bold=True, color=RED),
    # layout
    "layout.tree.row": Style(dim=False, color=RED),
    "layout.tree.column": Style(dim=False, color=BLUE),
    # log
    "logging.keyword": Style(bold=True, color=ORANGE),
    "logging.level.notset": Style(color=DARK_GREY, dim=True),
    "logging.level.trace": Style(color=GREY),
    "logging.level.debug": Style(color=LIGHT_GREY, bold=True),
    "logging.level.info": Style(color="white"),
    "logging.level.plugin": Style(color="cyan"),
    "logging.level.success": Style(color="green"),
    "logging.level.warning": Style(color="yellow"),
    "logging.level.error": Style(color="red"),
    "logging.level.critical": Style(color="red", bgcolor="#1e0010", bold=True),
    "log.level": Style.null(),
    "log.time": Style(color=CYAN, dim=True),
    "log.message": Style.null(),
    "log.path": Style(dim=True),
    "log.line_no": Style(color=CYAN, bold=True, italic=False, dim=True),
    # repr
    "repr.ellipsis": Style(color=YELLOW),
    "repr.indent": Style(color=GREEN, dim=True),
    "repr.error": Style(color=RED, bold=True),
    "repr.str": Style(color=GREEN, italic=False, bold=False),
    "repr.brace": Style(bold=True),
    "repr.comma": Style(bold=True),
    "repr.ipv4": Style(bold=True, color="bright_green"),
    "repr.ipv6": Style(bold=True, color="bright_green"),
    "repr.eui48": Style(bold=True, color="bright_green"),
    "repr.eui64": Style(bold=True, color="bright_green"),
    "repr.tag_start": Style(bold=True),
    "repr.tag_name": Style(color="bright_magenta", bold=True),
    "repr.tag_contents": Style(color="default"),
    "repr.tag_end": Style(bold=True),
    "repr.attrib_name": Style(color=YELLOW, italic=False),
    "repr.attrib_equal": Style(bold=True),
    "repr.attrib_value": Style(color=MAGENTA, italic=False),
    "repr.number": Style(color=CYAN, bold=True, italic=False),
    "repr.number_complex": Style(color=CYAN, bold=True, italic=False),  # same
    "repr.bool_true": Style(color="bright_green", italic=True),
    "repr.bool_false": Style(color="bright_red", italic=True),
    "repr.none": Style(color=MAGENTA, italic=True),
    "repr.url": Style(underline=True, color="bright_blue", italic=False, bold=False),
    "repr.uuid": Style(color="bright_yellow", bold=False),
    "repr.call": Style(color=MAGENTA, bold=True),
    "repr.path": Style(color=MAGENTA),
    "repr.filename": Style(color="bright_magenta"),
    "rule.line": Style(color="bright_green"),
    "rule.text": Style.null(),
    # json
    "json.brace": Style(bold=True),
    "json.bool_true": Style(color="bright_green", italic=True),
    "json.bool_false": Style(color="bright_red", italic=True),
    "json.null": Style(color=MAGENTA, italic=True),
    "json.number": Style(color=CYAN, bold=True, italic=False),
    "json.str": Style(color=GREEN, italic=False, bold=False),
    "json.key": Style(color=BLUE, bold=True),
    # prompt
    "prompt": Style.null(),
    "prompt.choices": Style(color=MAGENTA, bold=True),
    "prompt.default": Style(color=CYAN, bold=True),
    "prompt.invalid": Style(color=RED),
    "prompt.invalid.choice": Style(color=RED),
    # pretty
    "pretty": Style.null(),
    # scope
    "scope.border": Style(color=BLUE),
    "scope.key": Style(color=YELLOW, italic=True),
    "scope.key.special": Style(color=YELLOW, italic=True, dim=True),
    "scope.equals": Style(color=RED),
    # table
    "table.header": Style(bold=True),
    "table.footer": Style(bold=True),
    "table.cell": Style.null(),
    "table.title": Style(italic=True),
    "table.caption": Style(italic=True, dim=True),
    # traceback
    "traceback.error": Style(color=RED, italic=True),
    "traceback.border.syntax_error": Style(color="bright_red"),
    "traceback.border": Style(color=RED),
    "traceback.text": Style.null(),
    "traceback.title": Style(color=RED, bold=True),
    "traceback.exc_type": Style(color="bright_red", bold=True),
    "traceback.exc_value": Style.null(),
    "traceback.offset": Style(color="bright_red", bold=True),
    # bar
    "bar.back": Style(color="grey23"),
    "bar.complete": Style(color="rgb(249,38,114)"),
    "bar.finished": Style(color="rgb(114,156,31)"),
    "bar.pulse": Style(color="rgb(249,38,114)"),
    # progress
    "progress.description": Style.null(),
    "progress.filesize": Style(color=GREEN),
    "progress.filesize.total": Style(color=GREEN),
    "progress.download": Style(color=GREEN),
    "progress.elapsed": Style(color=YELLOW),
    "progress.percentage": Style(color=MAGENTA),
    "progress.remaining": Style(color=CYAN),
    "progress.data.speed": Style(color=RED),
    "progress.spinner": Style(color=GREEN),
    "status.spinner": Style(color=GREEN),
    # tree
    "tree": Style(),
    "tree.line": Style(),
    # markdown
    "markdown.paragraph": Style(),
    "markdown.text": Style(),
    "markdown.emph": Style(italic=True),
    "markdown.strong": Style(bold=True),
    "markdown.code": Style(bgcolor=BLACK, color="bright_white"),
    "markdown.code_block": Style(dim=True, color=CYAN, bgcolor=BLACK),
    "markdown.block_quote": Style(color=MAGENTA),
    "markdown.list": Style(color=CYAN),
    "markdown.item": Style(),
    "markdown.item.bullet": Style(color=YELLOW, bold=True),
    "markdown.item.number": Style(color=YELLOW, bold=True),
    "markdown.hr": Style(color=YELLOW),
    "markdown.h1.border": Style(),
    "markdown.h1": Style(bold=True),
    "markdown.h2": Style(bold=True, underline=True),
    "markdown.h3": Style(bold=True),
    "markdown.h4": Style(bold=True, dim=True),
    "markdown.h5": Style(underline=True),
    "markdown.h6": Style(italic=True),
    "markdown.h7": Style(italic=True, dim=True),
    "markdown.link": Style(color="bright_blue"),
    "markdown.link_url": Style(color=BLUE),
}
