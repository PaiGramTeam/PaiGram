import json
import asyncio
from pathlib import Path
from typing import Union

import aiofiles

from utils.const import DATA_DIR


PLAYER_SCRIPTS_PATH = DATA_DIR / "gcsim"
PLAYER_SCRIPTS_PATH.mkdir(parents=True, exist_ok=True)


class PlayerGCSimScripts:
    _lock = asyncio.Lock()

    def __init__(self, player_scripts_path: Path = PLAYER_SCRIPTS_PATH):
        self.player_scripts_path = player_scripts_path

    def get_player_path(self, uid: Union[str, int]):
        player_path = self.player_scripts_path.joinpath(str(uid))
        player_path.mkdir(parents=True, exist_ok=True)
        return player_path

    def get_script_path(self, uid: Union[str, int], script_key: str):
        scripts_path = self.get_player_path(str(uid)).joinpath("scripts")
        scripts_path.mkdir(parents=True, exist_ok=True)
        return scripts_path.joinpath(f"{script_key}.txt")

    def get_result_path(self, uid: Union[str, int], script_key: str):
        scripts_path = self.get_player_path(uid).joinpath("results")
        scripts_path.mkdir(parents=True, exist_ok=True)
        return scripts_path.joinpath(f"{script_key}.json")

    def get_fits_path(self, uid: Union[str, int]):
        return self.get_player_path(uid).joinpath("fits.json")

    def get_fits(self, uid: Union[str, int]) -> list[dict]:
        if self.get_fits_path(uid).exists():
            return json.loads(self.get_fits_path(uid).read_text(encoding="utf-8"))
        return []

    def remove_fits(self, uid: Union[str, int]):
        self.get_fits_path(uid).unlink(missing_ok=True)

    async def write_script(
        self,
        uid: Union[str, int],
        script_key: str,
        script: str,
    ):
        async with self._lock, aiofiles.open(self.get_script_path(uid, script_key), "w", encoding="utf-8") as f:
            await f.write(script)

    async def write_fits(self, uid: Union[str, int], fits: list[dict]):
        async with self._lock, aiofiles.open(self.get_fits_path(uid), "w", encoding="utf-8") as f:
            await f.write(json.dumps(fits, ensure_ascii=False, indent=4))
