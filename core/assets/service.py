from abc import ABC, abstractmethod
from pathlib import Path
from ssl import SSLZeroReturnError
from typing import ClassVar, Optional, Union

from aiofiles import open as async_open
from httpx import AsyncClient, HTTPError

from core.service import Service
from metadata.honey import HONEY_RESERVED_ID_MAP
from metadata.shortname import roleToId, roles
from modules.wiki.base import SCRAPE_HOST
from utils.const import PROJECT_ROOT
from utils.helpers import mkdir
from utils.typedefs import StrOrURL

ASSETS_PATH = PROJECT_ROOT.joinpath('resources/assets')
ASSETS_PATH.mkdir(exist_ok=True)


class _AssetsService(ABC):
    _dir: ClassVar[Path]

    id: str
    type: str

    @property
    def path(self) -> Path:
        return mkdir(self._dir.joinpath(self.id))

    def __init__(self, client: AsyncClient):
        self._client = client

    @abstractmethod
    def __call__(self, target):
        pass

    def __init_subclass__(cls, **kwargs):
        cls.type = cls.__name__.lstrip('_').split('Assets')[0].lower()
        cls._dir = ASSETS_PATH.joinpath(cls.type)
        cls._dir.mkdir(exist_ok=True)
        return cls

    async def _download(self, url: StrOrURL, path: Path, retry: int = 5) -> Optional[Path]:
        import asyncio
        for _ in range(retry):
            try:
                response = await self._client.get(url, follow_redirects=False)
            except (HTTPError, SSLZeroReturnError):
                await asyncio.sleep(1)
                continue
            if response.status_code != 200:
                return None
            async with async_open(path, 'wb') as file:
                await file.write(response.content)
            return path

    @abstractmethod
    async def icon(self) -> Path:
        pass


class _CharacterAssets(_AssetsService):
    # noinspection SpellCheckingInspection
    def __call__(self, target: Union[str, int]) -> "_CharacterAssets":
        if isinstance(target, int):
            if target == 10000005:
                self.id = 'playerboy_005'
            elif target == 10000007:
                self.id = 'playergirl_007'
            else:
                self.id = f"{roles[target][2]}_{str(target)[-3:]}"
        elif not target[-1].isdigit():
            target = roleToId(target)
            self.id = f"{roles[target][2]}_{str(target)[-3:]}"
        else:
            self.id = target
        return self

    async def icon(self) -> Path:
        if (path := self.path.joinpath('icon.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}_icon.webp')), path)

    async def side(self) -> Path:
        if (path := self.path.joinpath('side.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}_side_icon.webp')), path)

    async def gacha(self) -> Path:
        if (path := self.path.joinpath('gacha.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}_gacha_card.webp')), path)

    async def splash(self) -> Optional[Path]:
        if (path := self.path.joinpath('splash.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}_gacha_splash.webp')), path)


class _WeaponAssets(_AssetsService):
    def __call__(self, target: str) -> '_WeaponAssets':
        if not target[-1].isdigit():
            self.id = HONEY_RESERVED_ID_MAP['weapon'][target][0]
        else:
            self.id = target
        return self

    async def icon(self) -> Path:
        if (path := self.path.joinpath('icon.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}.webp')), path)

    async def awakened(self) -> Path:
        if (path := self.path.joinpath('awakened.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}_awaken_icon.webp')), path)

    async def gacha(self) -> Path:
        if (path := self.path.joinpath('gacha.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}_gacha_icon.webp')), path)


class _MaterialAssets(_AssetsService):

    def __call__(self, target) -> "_MaterialAssets":
        if not target[-1].isdigit():
            self.id = HONEY_RESERVED_ID_MAP['material'][target][0]
        else:
            self.id = target
        return self

    async def icon(self) -> Path:
        if (path := self.path.joinpath('icon.webp')).exists():
            return path

        return await self._download(SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.id}.webp')), path)


class AssetsService(Service):
    """asset服务

    用于储存和管理 asset :
        当对应的 asset (如某角色图标)不存在时，该服务会先查找本地。
        若本地不存在，则从网络上下载；若存在，则返回其路径
    """

    character: _CharacterAssets
    weapon: _WeaponAssets
    material: _MaterialAssets

    def __init__(self):
        self.client = AsyncClient()
        self.character = _CharacterAssets(self.client)
        self.weapon = _WeaponAssets(self.client)
        self.material = _MaterialAssets(self.client)
