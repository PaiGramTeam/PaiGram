import asyncio
from pathlib import Path
from typing import Union

import aiofiles

from utils.const import PROJECT_ROOT


PLAYER_SCRIPTS_PATH = PROJECT_ROOT.joinpath("plugins", "genshin", "gcsim", "scripts", "players")
PLAYER_SCRIPTS_PATH.mkdir(parents=True, exist_ok=True)


class PlayerGCSimScripts:
    _lock = asyncio.Lock()

    def __init__(self, player_scripts_path: Path = PLAYER_SCRIPTS_PATH):
        self.player_scripts_path = player_scripts_path

    def get_script_path(self, uid: Union[str, int], script_key: str):
        scripts_path = self.player_scripts_path.joinpath(str(uid)).joinpath("scripts")
        scripts_path.mkdir(parents=True, exist_ok=True)
        return scripts_path.joinpath(f"{script_key}.txt")

    def get_result_path(self, uid: Union[str, int], script_key: str):
        scripts_path = self.player_scripts_path.joinpath(str(uid)).joinpath("results")
        scripts_path.mkdir(parents=True, exist_ok=True)
        return scripts_path.joinpath(f"{script_key}.json")

    async def write_script(
        self,
        uid: Union[str, int],
        script_key: str,
        script: str,
    ):
        async with self._lock, aiofiles.open(self.get_script_path(uid, script_key), "w", encoding="utf-8") as f:
            await f.write(script)
