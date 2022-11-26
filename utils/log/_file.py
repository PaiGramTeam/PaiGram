import os
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import IO, AnyStr, Iterable, Iterator, List, Optional, Type

__all__ = ["FileIO"]


# noinspection SpellCheckingInspection
class FileIO(IO[str]):
    def __init__(self, path: Path):
        self.path = path.parent.resolve()
        self.file = path
        self.file_stream: Optional[IO[str]] = None

    def _get_file(self) -> IO[str]:
        today = date.today()
        if self.file.exists():
            if not self.file.is_file():
                raise FileExistsError(f'Log file conflict, please delete the folder "{str(self.file.resolve())}"')
            if self.file_stream is None or self.file_stream.closed:
                self.file_stream = self.file.open(mode="a+", encoding="utf-8")
            modify_date = date.fromtimestamp(os.stat(self.file).st_mtime)
        else:
            self.file_stream = self.file.open(mode="a+", encoding="utf-8")
            modify_date = today
        if modify_date < today:
            if self.file_stream is not None and not self.file_stream.closed:
                self.file_stream.close()
            log_path = self.path.joinpath(f'{modify_date.strftime("%Y-%m-%d")}.log')
            if log_path.exists():
                # 转存日志
                with open(log_path, mode="a+", encoding="utf-8") as file:
                    file.write("\n")
                    with open(self.file, mode="r+", encoding="utf-8") as f:
                        file.writelines(f.readlines())
            else:
                self.file.rename(self.path.joinpath(f'{modify_date.strftime("%Y-%m-%d")}.log'))
            self.file_stream = self.file.open(mode="a+", encoding="utf-8")
        return self.file_stream

    def close(self) -> None:
        return self._get_file().close()

    def fileno(self) -> int:
        return self._get_file().fileno()

    def flush(self) -> None:
        return self._get_file().flush()

    def isatty(self) -> bool:
        return self._get_file().isatty()

    def read(self, __n: int = -1) -> AnyStr:
        return self._get_file().read(__n)

    def readable(self) -> bool:
        return self._get_file().readable()

    def readline(self, __limit: int = ...) -> AnyStr:
        return self._get_file().readline()

    def readlines(self, __hint: int = ...) -> List[AnyStr]:
        return self._get_file().readlines()

    def seek(self, __offset: int, __whence: int = 0) -> int:
        return self._get_file().seek(__offset, __whence)

    def seekable(self) -> bool:
        return self._get_file().seekable()

    def tell(self) -> int:
        return self._get_file().tell()

    def truncate(self, __size: Optional[int] = None) -> int:
        return self._get_file().truncate(__size)

    def writable(self) -> bool:
        return self._get_file().writable()

    def write(self, __s: AnyStr) -> int:
        return self._get_file().write(__s)

    def writelines(self, __lines: Iterable[AnyStr]) -> None:
        return self._get_file().writelines(__lines)

    def __next__(self) -> AnyStr:
        return self._get_file().__next__()

    def __iter__(self) -> Iterator[AnyStr]:
        return self._get_file().__iter__()

    def __enter__(self) -> IO[AnyStr]:
        return self._get_file().__enter__()

    def __exit__(
        self, __t: Optional[Type[BaseException]], __value: Optional[BaseException], __traceback: Optional[TracebackType]
    ) -> None:
        return self._get_file().__exit__(__t, __value, __traceback)
