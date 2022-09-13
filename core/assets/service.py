import asyncio
from pathlib import Path
from typing import List, Optional, Union

from aiofiles import open as async_open
from httpx import AsyncClient, HTTPError

from core.service import Service
from metadata.shortname import roleToId, roles, weaponToName
from modules.wiki.character import Character
from modules.wiki.weapon import Weapon
from utils.const import PROJECT_ROOT
from utils.helpers import mkdir

ASSETS_PATH = PROJECT_ROOT.joinpath('resources/assets')
ASSETS_PATH.mkdir(exist_ok=True)


class AssetsService(Service):
    """asset服务

    用于储存和管理 asset :
        当对应的 asset (如某角色图标)不存在时，该服务会先查找本地。
        若本地不存在，则从网络上下载；若存在，则返回其路径
    """

    def __init__(self):
        self.client = AsyncClient()

    # noinspection PyUnboundLocalVariable
    async def _download(self, url, path: Path, retry: int = 5) -> Optional[Path]:
        for _ in range(retry):
            try:
                response = await self.client.get(url)
            except HTTPError:
                await asyncio.sleep(1)
                continue
            async with async_open(path, 'wb') as file:
                await file.write(response.content)
            return path

    # noinspection SpellCheckingInspection
    async def character_icon(self, target: Union[int, str]) -> List[Path]:
        if isinstance(target, int):
            if target == 10000005:
                cid = 'playerboy_005'
            elif target == 10000007:
                cid = 'playergirl_007'
            else:
                cid = f"{roles[target][2]}_{str(target)[-3:]}"
        elif not target[-1].isdigit():
            target = roleToId(target)
            cid = f"{roles[target][2]}_{str(target)[-3:]}"
        else:
            cid = target
        if (path := ASSETS_PATH.joinpath(f"character/{cid}")).exists() and (result := list(path.iterdir())):
            return list(map(lambda x: x.resolve(), filter(lambda x: x, result)))
        else:
            mkdir(path)
            character = await Character.get_by_id(cid)
            result = []
            for icon_type, url in character.icon.dict().items():
                result.append(await self._download(url, path.joinpath(f"{icon_type}.webp")))
            return list(map(lambda x: x.resolve(), filter(lambda x: x, result)))

    async def weapon_icon(self, target: Union[int, str]) -> List[Path]:
        if isinstance(target, int):
            weapon = await Weapon.get_by_id(f"i_n{target}")
        elif not target[-1].isdigit():
            weapon = await Weapon.get_by_name(weaponToName(target))
        else:
            weapon = await Weapon.get_by_id(target)
        if (path := ASSETS_PATH.joinpath(f"weapon/{weapon.id}")).exists() and (result := list(path.iterdir())):
            return list(map(lambda x: x.resolve(), filter(lambda x: x, result)))
        else:
            mkdir(path)
            result = []
            for icon_type, url in weapon.icon.dict().items():
                result.append(await self._download(url, path.joinpath(f"{icon_type}.webp")))
            return list(map(lambda x: x.resolve(), filter(lambda x: x, result)))
