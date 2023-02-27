import inspect
import multiprocessing
import os
import signal
import threading
from pathlib import Path
from typing import Callable, Iterator, List, Optional, TYPE_CHECKING

from watchfiles import watch

from utils.const import HANDLED_SIGNALS, PROJECT_ROOT
from utils.log import logger
from utils.typedefs import StrOrPath

if TYPE_CHECKING:
    from multiprocessing.process import BaseProcess

__all__ = ("Reloader",)

multiprocessing.allow_connection_pickling()
spawn = multiprocessing.get_context("spawn")


class FileFilter:
    """监控文件过滤"""

    def __init__(self, includes: List[str], excludes: List[str]) -> None:
        default_includes = ["*.py"]
        self.includes = [default for default in default_includes if default not in excludes]
        self.includes.extend(includes)
        self.includes = list(set(self.includes))

        default_excludes = [".*", ".py[cod]", ".sw.*", "~*", __file__]
        self.excludes = [default for default in default_excludes if default not in includes]
        self.exclude_dirs = []
        for e in excludes:
            p = Path(e)
            try:
                is_dir = p.is_dir()
            except OSError:
                is_dir = False

            if is_dir:
                self.exclude_dirs.append(p)
            else:
                self.excludes.append(e)
        self.excludes = list(set(self.excludes))

    def __call__(self, path: Path) -> bool:
        for include_pattern in self.includes:
            if path.match(include_pattern):
                for exclude_dir in self.exclude_dirs:
                    if exclude_dir in path.parents:
                        return False

                for exclude_pattern in self.excludes:
                    if path.match(exclude_pattern):
                        return False

                return True
        return False


class Reloader:
    _target: Callable[..., None]
    _process: "BaseProcess"

    @property
    def process(self) -> "BaseProcess":
        return self._process

    @property
    def target(self) -> Callable[..., None]:
        return self._target

    def __init__(
        self,
        target: Callable[..., None],
        *,
        reload_delay: float = 0.25,
        reload_dirs: List[StrOrPath] = None,
        reload_includes: List[str] = None,
        reload_excludes: List[str] = None,
    ):
        if inspect.iscoroutinefunction(target):
            raise ValueError("不支持异步函数")
        self._target = target

        self.reload_delay = reload_delay

        _reload_dirs = []
        for reload_dir in reload_dirs or []:
            _reload_dirs.append(PROJECT_ROOT.joinpath(Path(reload_dir)))

        self.reload_dirs = []
        for reload_dir in _reload_dirs:
            append = True
            for parent in reload_dir.parents:
                if parent in _reload_dirs:
                    append = False
                    break
            if append:
                self.reload_dirs.append(reload_dir)

        if not self.reload_dirs:
            logger.warning("需要检测的目标文件夹列表为空", extra={"tag": "Reloader"})

        self._should_exit = threading.Event()

        frame = inspect.currentframe().f_back

        self.watch_filter = FileFilter(reload_includes or [], (reload_excludes or []) + [frame.f_globals["__file__"]])
        self.watcher = watch(
            *self.reload_dirs,
            watch_filter=None,
            stop_event=self._should_exit,
            yield_on_timeout=True,
        )

    def get_changes(self) -> Optional[List[Path]]:
        if not self._process.is_alive():
            logger.info("目标进程已经关闭", extra={"tag": "Reloader"})
            self._should_exit.set()
        try:
            changes = next(self.watcher)
        except StopIteration:
            return None
        if changes:
            unique_paths = {Path(c[1]) for c in changes}
            return [p for p in unique_paths if self.watch_filter(p)]
        return None

    def __iter__(self) -> Iterator[Optional[List[Path]]]:
        return self

    def __next__(self) -> Optional[List[Path]]:
        return self.get_changes()

    def run(self) -> None:
        self.startup()
        for changes in self:
            if changes:
                logger.warning(
                    "检测到文件 %s 发生改变, 正在重载...",
                    [str(c.relative_to(PROJECT_ROOT)).replace(os.sep, "/") for c in changes],
                    extra={"tag": "Reloader"},
                )
                self.restart()

        self.shutdown()

    def signal_handler(self, *_) -> None:
        """当接收到结束信号量时"""
        self._process.join(3)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join()
        self._should_exit.set()

    def startup(self) -> None:
        """启动进程"""
        logger.info("目标进程正在启动", extra={"tag": "Reloader"})

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

        self._process = spawn.Process(target=self._target)
        self._process.start()
        logger.success("目标进程启动成功", extra={"tag": "Reloader"})

    def restart(self) -> None:
        """重启进程"""
        self._process.terminate()
        self._process.join(10)

        self._process = spawn.Process(target=self._target)
        self._process.start()
        logger.info("目标进程已经重载", extra={"tag": "Reloader"})

    def shutdown(self) -> None:
        """关闭进程"""
        self._process.terminate()
        self._process.join(10)

        logger.info("重载器已经关闭", extra={"tag": "Reloader"})
