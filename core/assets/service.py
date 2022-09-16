import asyncio
from pathlib import Path
from typing import Dict, Optional, Union

from aiofiles import open as async_open
from httpx import AsyncClient, HTTPError

from core.service import Service
from metadata.honey import HONEY_ID_MAP, HONEY_RESERVED_ID_MAP
from metadata.shortname import roleToId, roles
from modules.wiki.base import SCRAPE_HOST
from utils.const import PROJECT_ROOT
from utils.helpers import mkdir
from utils.log import logger

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
                response = await self.client.get(url, follow_redirects=False)
            except HTTPError:
                await asyncio.sleep(1)
                continue
            if response.status_code != 200:
                return None
            async with async_open(path, 'wb') as file:
                await file.write(response.content)
            return path

    # noinspection SpellCheckingInspection
    async def character_icon(self, target: Union[int, str]) -> Dict[str, Path]:
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
            return {p.stem: p for p in map(lambda x: x.resolve(), filter(lambda x: x, result))}
        else:
            result = []
            icons = {
                "icon": str(SCRAPE_HOST.join(f'/img/{cid}_icon.webp')),
                "side": str(SCRAPE_HOST.join(f'/img/{cid}_side_icon.webp')),
                "gacha": str(SCRAPE_HOST.join(f'/img/{cid}_gacha_card.webp')),
                "splash": str(SCRAPE_HOST.join(f'/img/{cid}_gacha_splash.webp'))
            }
            character = HONEY_ID_MAP['character'][cid]
            logger.info(f"正在下载 \"{character[0]}\" 的图标")
            for icon_type, url in icons.items():
                result.append(await self._download(url, mkdir(path).joinpath(f"{icon_type}.webp")))
            return {p.stem: p for p in map(lambda x: x.resolve(), filter(lambda x: x, result))}

    async def weapon_icon(self, target: str) -> Dict[str, Path]:
        if not target[-1].isdigit():
            wid = HONEY_RESERVED_ID_MAP['weapon'][target][0]
        else:
            wid = target
        if (path := ASSETS_PATH.joinpath(f"weapon/{wid}")).exists() and (result := list(path.iterdir())):
            return {p.stem: p for p in map(lambda x: x.resolve(), filter(lambda x: x, result))}
        else:
            result = []
            icons = {
                "icon": str(SCRAPE_HOST.join(f'/img/{wid}.webp')),
                "awakened": str(SCRAPE_HOST.join(f'/img/{wid}_awaken_icon.webp')),
                "gacha": str(SCRAPE_HOST.join(f'/img/{wid}_gacha_icon.webp')),
            }
            weapon = HONEY_ID_MAP['weapon'][wid]
            logger.info(f"正在下载 \"{weapon[0]}\" 的图标")
            for icon_type, url in icons.items():
                result.append(await self._download(url, mkdir(path).joinpath(f"{icon_type}.webp")))
            return {p.stem: p for p in map(lambda x: x.resolve(), filter(lambda x: x, result))}

    async def material_icon(self, target: str) -> Path:
        if not target[-1].isdigit():
            mid = HONEY_RESERVED_ID_MAP['material'][target][0]
        else:
            mid = target
        if (path := ASSETS_PATH.joinpath(f'material/{mid}.webp')).exists():
            return path
        else:
            icon = str(SCRAPE_HOST.join(f'/img/{mid}.webp'))
            material = HONEY_ID_MAP['material'][mid]
            logger.info(f"正在下载 \"{material[0]}\" 的图标")
            return await self._download(icon, mkdir(path))
