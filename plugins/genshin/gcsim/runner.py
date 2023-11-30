import asyncio
import multiprocessing
import platform
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from queue import Queue
from typing import Optional, Dict, List, Union

import aiofiles
import gcsim_pypi

from core.config import config
from metadata.shortname import idToName
from modules.gcsim.file import PlayerGCSimScripts
from plugins.genshin.model.base import CharacterInfo
from plugins.genshin.model.converters.gcsim import GCSimConverter
from plugins.genshin.model.gcsim import GCSim
from utils.const import PROJECT_ROOT
from utils.log import logger

GCSIM_SCRIPTS_PATH = PROJECT_ROOT.joinpath("plugins", "genshin", "gcsim", "scripts")


@dataclass
class GCSimFit:
    script_key: str
    fit_count: int
    characters: List[str]
    total_levels: int
    total_weapon_levels: int


@dataclass
class GCSimResult:
    error: Optional[str]
    user_id: str
    uid: str
    script_key: str


def _get_gcsim_bin_name() -> str:
    if platform.system() == "Windows":
        return "gcsim.exe"
    bin_name = "gcsim"
    if platform.system() == "Darwin":
        bin_name += ".darwin"
    if platform.machine() == "arm64":
        bin_name += ".arm64"
    return bin_name


class GCSimRunner:
    def __init__(self):
        self.initialized = False
        self.bin_path = None
        self.player_gcsim_scripts = PlayerGCSimScripts()
        self.gcsim_version: Optional[str] = None
        self.scripts: Dict[str, GCSim] = {}
        max_concurrent_gcsim = multiprocessing.cpu_count()
        self.sema = asyncio.BoundedSemaphore(max_concurrent_gcsim)
        self.queue: Queue[None] = Queue()

    async def initialize(self):
        gcsim_pypi_path = Path(gcsim_pypi.__file__).parent

        self.bin_path = gcsim_pypi_path.joinpath("bin").joinpath(_get_gcsim_bin_name())
        result = subprocess.run([self.bin_path, "-version"], capture_output=True, text=True, check=True)
        if result.returncode == 0:
            self.gcsim_version = result.stdout.splitlines()[0]

        now = time.time()
        for path in GCSIM_SCRIPTS_PATH.iterdir():
            if path.is_file():
                try:
                    async with aiofiles.open(path, "r") as f:
                        script = GCSimConverter.from_gcsim_script(await f.read())
                    self.scripts[path.stem] = script
                except ValueError as e:
                    logger.error("无法解析 GCSim 脚本 %s: %s", path.name, e)
        logger.debug("加载 %d GCSim 脚本耗时 %.2f 秒", len(self.scripts), time.time() - now)
        self.initialized = True

    async def _execute_gcsim(
        self, user_id: str, uid: str, script_key: str, added_time: float, character_infos: List[CharacterInfo]
    ) -> GCSimResult:
        script = self.scripts.get(script_key)
        if script is None:
            return GCSimResult(error="未找到脚本", user_id=user_id, uid=uid, script_key=script_key)
        try:
            merged_script = GCSimConverter.merge_character_infos(script, character_infos)
        except ValueError:
            return GCSimResult(error="无法合并角色信息", user_id=user_id, uid=uid, script_key=script_key)
        await self.player_gcsim_scripts.write_script(uid, script_key, str(merged_script))

        process = await asyncio.create_subprocess_exec(
            self.bin_path,
            "-c",
            self.player_gcsim_scripts.get_script_path(uid, script_key).absolute().as_posix(),
            "-out",
            self.player_gcsim_scripts.get_result_path(uid, script_key).absolute().as_posix(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        logger.debug("GCSim 脚本 (%s|%s|%s) 用时 %.2fs", user_id, uid, script_key, time.time() - added_time)
        if stderr:
            logger.error("GCSim 脚本 (%s|%s|%s) 错误: %s", user_id, uid, script_key, stderr.decode("utf-8"))
            return GCSimResult(error=stderr.decode("utf-8"), user_id=user_id, uid=uid, script_key=script_key)
        if stdout:
            logger.debug("GCSim 脚本 (%s|%s|%s) 输出: %s", user_id, uid, script_key, stdout.decode("utf-8"))
            return GCSimResult(error=None, user_id=user_id, uid=uid, script_key=script_key)
        return GCSimResult(error="No output", user_id=user_id, uid=uid, script_key=script_key)

    async def run(
        self,
        user_id: str,
        uid: str,
        script_key: str,
        character_infos: List[CharacterInfo],
    ) -> GCSimResult:
        start_time = time.time()
        async with self.sema:
            result = await self._execute_gcsim(user_id, uid, script_key, start_time, character_infos)
            return result

    async def calculate_fits(self, uid: Union[int, str], character_infos: List[CharacterInfo]) -> List[GCSimFit]:
        fits = []
        for key, script in self.scripts.items():
            # 空和莹会被认为是两个角色
            fit_characters = []
            for ch in character_infos:
                if GCSimConverter.from_character(ch.character) in [c.character for c in script.characters]:
                    fit_characters.append(ch)
            if fit_characters:
                fits.append(
                    GCSimFit(
                        script_key=key,
                        characters=[idToName(ch.id) for ch in fit_characters],
                        fit_count=len(fit_characters),
                        total_levels=sum(ch.level for ch in script.characters),
                        total_weapon_levels=sum(ch.weapon_info.level for ch in script.characters),
                    )
                )
        fits = sorted(
            fits,
            key=lambda x: (x.fit_count, x.total_levels, x.total_weapon_levels),
            reverse=True,
        )
        await self.player_gcsim_scripts.write_fits(uid, [asdict(fit) for fit in fits])
        return fits

    async def get_fits(self, uid: Union[int, str]) -> List[GCSimFit]:
        return [GCSimFit(**fit) for fit in self.player_gcsim_scripts.get_fits(uid)]
