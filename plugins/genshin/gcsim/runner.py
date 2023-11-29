import time
import copy
import shutil
import asyncio
import platform
import threading
import subprocess
import multiprocessing
from hashlib import md5
from queue import Queue
from pathlib import Path
from dataclasses import dataclass
from asyncio.subprocess import Process  # noqa
from typing import Optional, Dict, TYPE_CHECKING, List, Tuple, Union

import aiofiles
import gcsim_pypi
from enkanetwork import Assets, EnkaNetworkResponse

from core.config import config
from utils.log import logger
from utils.const import PROJECT_ROOT
from metadata.shortname import idToName
from modules.playercards.file import PlayerCardsFile
from modules.gcsim.file import PlayerGCSimScripts
from plugins.genshin.model.gcsim import GCSim
from plugins.genshin.model.base import CharacterInfo
from plugins.genshin.model.converters.enka import EnkaConverter
from plugins.genshin.model.converters.gcsim import GCSimConverter


GCSIM_SCRIPTS_PATH = PROJECT_ROOT.joinpath("plugins", "genshin", "gcsim", "scripts", "gcdatabase")


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
        self.max_concurrent_gcsim = (
            config.plugin_gcsim_max_concurrent
            if isinstance(config.plugin_gcsim_max_concurrent, int)
            else 0
            if config.plugin_gcsim_max_concurrent == "NONE"
            else 1
            if config.plugin_gcsim_max_concurrent == "ONE"
            else multiprocessing.cpu_count() / 2
            if config.plugin_gcsim_max_concurrent == "HALF"
            else multiprocessing.cpu_count()
        )
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
        logger.debug(f"GCSim 脚本 ({user_id}|{uid}|{script_key}) 用时 {time.time()-added_time:.2f}s")
        if stderr:
            logger.error(f"GCSim 脚本 ({user_id}|{uid}|{script_key}) 错误: {stderr.decode('utf-8')}")
            return GCSimResult(error=stderr.decode("utf-8"), user_id=user_id, uid=uid, script_key=script_key)
        elif stdout:
            logger.debug(f"GCSim 脚本 ({user_id}|{uid}|{script_key}) 输出: {stdout.decode('utf-8')}")
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
        while True:
            while self.queue.qsize() < self.max_concurrent_gcsim:
                self.queue.put(None)
                try:
                    result = await self._execute_gcsim(user_id, uid, script_key, start_time, character_infos)
                finally:
                    self.queue.get()
                return result
            await asyncio.sleep(0.1)

    async def calculate_fits(self, character_infos: List[CharacterInfo]) -> List[GCSimFit]:
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
        return sorted(
            fits,
            key=lambda x: (x.fit_count, x.total_levels, x.total_weapon_levels),
            reverse=True,
        )
