import asyncio
import multiprocessing
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Optional, Dict, List, Union, TYPE_CHECKING, Tuple

import gcsim_pypi
from pydantic import BaseModel

from metadata.shortname import idToName
from modules.apihelper.client.components.remote import Remote
from modules.gcsim.cache import GCSimCache
from modules.gcsim.file import PlayerGCSimScripts
from plugins.genshin.model.base import CharacterInfo, Character
from plugins.genshin.model.converters.gcsim import GCSimConverter
from plugins.genshin.model.gcsim import GCSim, GCSimCharacter
from utils.const import DATA_DIR
from utils.log import logger

if TYPE_CHECKING:
    from core.dependence.redisdb import RedisDB

GCSIM_SCRIPTS_PATH = DATA_DIR / "gcsim" / "scripts"
GCSIM_SCRIPTS_PATH.mkdir(parents=True, exist_ok=True)


class FitCharacter(BaseModel):
    id: int
    name: str
    gcsim: GCSimCharacter
    character: Character

    def __str__(self):
        return self.name


class GCSimFit(BaseModel):
    script_key: str
    fit_count: int
    characters: List[FitCharacter]
    total_levels: int
    total_weapon_levels: int


@dataclass
class GCSimResult:
    error: Optional[str]
    user_id: str
    uid: str
    script_key: str
    script: Optional[GCSim] = None
    file_id: Optional[str] = None


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
    def __init__(self, client: "RedisDB"):
        self.initialized = False
        self.bin_path = None
        self.player_gcsim_scripts = PlayerGCSimScripts()
        self.gcsim_version: Optional[str] = None
        self.scripts: Dict[str, GCSim] = {}
        max_concurrent_gcsim = multiprocessing.cpu_count()
        self.sema = asyncio.BoundedSemaphore(max_concurrent_gcsim)
        self.queue: Queue[None] = Queue()
        self.cache = GCSimCache(client)

    @staticmethod
    def check_gcsim_script(name: str, script: str) -> Optional[GCSim]:
        try:
            return GCSimConverter.from_gcsim_script(script)
        except ValueError as e:
            logger.error("无法解析 GCSim 脚本 %s: %s", name, e)
            return None

    async def refresh(self):
        self.player_gcsim_scripts.clear_fits()
        self.scripts.clear()
        new_scripts = await Remote.get_gcsim_scripts()
        for name, text in new_scripts.items():
            if script := self.check_gcsim_script(name, text):
                self.scripts[name] = script
        for path in GCSIM_SCRIPTS_PATH.iterdir():
            if path.is_file():
                with open(path, "r", encoding="utf-8") as f:
                    try:
                        if script := self.check_gcsim_script(path.name, f.read()):
                            self.scripts[path.stem] = script
                    except UnicodeError as e:
                        logger.error("无法读取 GCSim 脚本 %s: %s", path.name, e)

    async def initialize(self):
        gcsim_pypi_path = Path(gcsim_pypi.__file__).parent

        self.bin_path = gcsim_pypi_path.joinpath("bin").joinpath(_get_gcsim_bin_name())

        process = await asyncio.create_subprocess_exec(
            self.bin_path, "-version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            self.gcsim_version = stdout.decode().splitlines()[0]
            logger.debug("GCSim version: %s", self.gcsim_version)
        else:
            logger.error("GCSim 运行时出错: %s", stderr.decode())

        now = time.time()
        await self.refresh()
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
        if file_id := await self.cache.get_cache(uid, hash(str(merged_script))):
            return GCSimResult(error=None, user_id=user_id, uid=uid, script_key=script_key, file_id=file_id)
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
            logger.error("GCSim 脚本 (%s|%s|%s) 错误: %s", user_id, uid, script_key, stderr.decode())
            return GCSimResult(
                error=stderr.decode(), user_id=user_id, uid=uid, script_key=script_key, script=merged_script
            )
        if stdout:
            logger.debug("GCSim 脚本 (%s|%s|%s) 输出: %s", user_id, uid, script_key, stdout.decode())
            return GCSimResult(error=None, user_id=user_id, uid=uid, script_key=script_key, script=merged_script)
        return GCSimResult(
            error="No output",
            user_id=user_id,
            uid=uid,
            script_key=script_key,
            script=merged_script,
        )

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
            fit_characters: List[Tuple[CharacterInfo, GCSimCharacter]] = []
            for ch in character_infos:
                gcsim_character = GCSimConverter.from_character(ch.character)
                if gcsim_character in [c for c in script.characters]:
                    fit_characters.append((ch, gcsim_character))
            if fit_characters:
                fits.append(
                    GCSimFit(
                        script_key=key,
                        characters=[
                            FitCharacter(id=ch[0].id, name=idToName(ch[0].id), gcsim=ch[1], character=ch[0].character)
                            for ch in fit_characters
                        ],
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
        await self.player_gcsim_scripts.write_fits(uid, [fit.dict() for fit in fits])
        return fits

    async def get_fits(self, uid: Union[int, str]) -> List[GCSimFit]:
        return [GCSimFit(**fit) for fit in self.player_gcsim_scripts.get_fits(uid)]

    async def remove_fits(self, uid: Union[int, str]) -> None:
        self.player_gcsim_scripts.remove_fits(uid)
