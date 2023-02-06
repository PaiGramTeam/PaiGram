import hashlib
import os
import re
from abc import ABC
from asyncio import create_subprocess_shell
from functools import lru_cache
from inspect import isabstract as inspect_isabstract, iscoroutinefunction
from pathlib import Path
from typing import Awaitable, Callable, Iterator, Match, Pattern, Type, TypeVar, Union

from typing_extensions import ParamSpec

__all__ = [
    "sha1",
    "gen_pkg",
    "async_re_sub",
    "execute",
    "isabstract",
]

T = TypeVar("T")
P = ParamSpec("P")


@lru_cache(64)
def sha1(text: str) -> str:
    _sha1 = hashlib.sha1()
    _sha1.update(text.encode())
    return _sha1.hexdigest()


async def execute(command: Union[str, bytes], pass_error: bool = True) -> str:
    """Executes command and returns output, with the option of enabling stderr."""
    from asyncio import subprocess

    executor = await create_subprocess_shell(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
    )

    stdout, stderr = await executor.communicate()
    if pass_error:
        try:
            result = str(stdout.decode().strip()) + str(stderr.decode().strip())
        except UnicodeDecodeError:
            result = str(stdout.decode("gbk").strip()) + str(stderr.decode("gbk").strip())
    else:
        try:
            result = str(stdout.decode().strip())
        except UnicodeDecodeError:
            result = str(stdout.decode("gbk").strip())
    return result


async def async_re_sub(
    pattern: Union[str, Pattern],
    repl: Union[str, Callable[[Match], Union[Awaitable[str], str]]],
    string: str,
    count: int = 0,
    flags: int = 0,
) -> str:
    """
    一个支持 repl 参数为 async 函数的 re.sub
    Args:
        pattern (str | Pattern): 正则对象
        repl (str | Callable[[Match], str] | Callable[[Match], Awaitable[str]]): 替换后的文本或函数
        string (str): 目标文本
        count (int): 要替换的最大次数
        flags (int): 标志常量

    Returns:
        返回经替换后的字符串
    """
    result = ""
    temp = string
    if count != 0:
        for _ in range(count):
            match = re.search(pattern, temp, flags=flags)
            replaced = None
            if iscoroutinefunction(repl):
                # noinspection PyUnresolvedReferences,PyCallingNonCallable
                replaced = await repl(match)
            elif callable(repl):
                # noinspection PyCallingNonCallable
                replaced = repl(match)
            result += temp[: match.span(1)[0]] + (replaced or repl)
            temp = temp[match.span(1)[1] :]
    else:
        while match := re.search(pattern, temp, flags=flags):
            replaced = None
            if iscoroutinefunction(repl):
                # noinspection PyUnresolvedReferences,PyCallingNonCallable
                replaced = await repl(match)
            elif callable(repl):
                # noinspection PyCallingNonCallable
                replaced = repl(match)
            result += temp[: match.span(1)[0]] + (replaced or repl)
            temp = temp[match.span(1)[1] :]
    return result + temp


def gen_pkg(path: Path) -> Iterator[str]:
    """遍历 path 生成可以用于 import_module 导入的字符串

    注意: 此方法会遍历当前目录下所有的、文件名为以非 '_' 开头的 '.py' 文件，并将他们导入
    """
    from utils.const import PROJECT_ROOT

    for p in path.iterdir():
        if not p.name.startswith("_"):
            if p.is_dir():
                yield from gen_pkg(p)
            elif p.suffix == ".py":
                yield str(p.relative_to(PROJECT_ROOT).with_suffix("")).replace(os.sep, ".")


def isabstract(target: Type) -> bool:
    return any([inspect_isabstract(target), isinstance(target, type) and ABC in target.__bases__])
