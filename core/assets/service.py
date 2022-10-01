import asyncio
from abc import ABC, abstractmethod
from functools import cached_property, partial
from multiprocessing import RLock as Lock
from pathlib import Path
from ssl import SSLZeroReturnError
from typing import Awaitable, Callable, ClassVar, Dict, List, Optional, TYPE_CHECKING, TypeVar, Union

from aiofiles import open as async_open
from aiofiles.os import remove as async_remove
from enkanetwork import Assets as EnkaAssets
from enkanetwork.model.assets import CharacterAsset as EnkaCharacterAsset
from httpx import AsyncClient, HTTPError, URL
from typing_extensions import Self

from core.service import Service
from metadata.honey import HONEY_DATA, weapon_to_icon_name
from modules.wiki.base import SCRAPE_HOST
from utils.const import PROJECT_ROOT
from utils.log import logger
from utils.typedefs import StrOrURL

if TYPE_CHECKING:
    from multiprocessing.synchronize import RLock

ENKA_HOST = URL("https://enka.network/ui/")

ASSETS_PATH = PROJECT_ROOT.joinpath('resources/assets')
ASSETS_PATH.mkdir(exist_ok=True, parents=True)

ICON_TYPE = Union[
    Callable[[bool], Awaitable[Optional[Path]]],
    Callable[..., Awaitable[Optional[Path]]]
]
URL_MAP_TYPE = Dict[str, Union[str, List[str]]]


class _AssetsService(ABC):
    _lock: ClassVar['RLock'] = Lock()
    _dir: ClassVar[Path]
    icon_types: ClassVar[List[str]]

    id: int
    type: str

    icon: ICON_TYPE

    @abstractmethod
    @cached_property
    def honey_id(self) -> str:
        """当前资源在 Honey Impact 所对应的 ID"""

    @abstractmethod
    @cached_property
    def url_map(self) -> URL_MAP_TYPE:
        """用于储存honey网址的map"""

    @property
    def path(self) -> Path:
        """当前资源的文件夹"""
        result = self._dir.joinpath(str(self.id)).resolve()
        result.mkdir(exist_ok=True, parents=True)
        return result

    @property
    def client(self) -> AsyncClient:
        with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = AsyncClient()
        return self._client

    def __init__(self, client: Optional[AsyncClient] = None) -> None:
        self._client = client

    def __call__(self, target: int) -> Self:
        result = self.__class__(self._client)
        result.id = target
        return result

    def __init_subclass__(cls, **kwargs) -> None:
        """初始化一些类变量"""
        from itertools import chain
        cls.icon_types = [
            k
            for k, v in
            chain(
                cls.__annotations__.items(),
                *map(
                    lambda x: x.__annotations__.items(),
                    cls.__bases__
                )
            )
            if v == ICON_TYPE
        ]
        cls.type = cls.__name__.lstrip('_').split('Assets')[0].lower()
        cls._dir = ASSETS_PATH.joinpath(cls.type)
        cls._dir.mkdir(exist_ok=True, parents=True)

    async def _download(self, url: StrOrURL, path: Path, retry: int = 5) -> Optional[Path]:
        logger.debug(f"正在从 {url} 下载图标至 {path}")
        for time in range(retry + 1):
            try:
                response = await self.client.get(url, follow_redirects=False)
            except Exception as error:
                if not isinstance(error, (HTTPError, SSLZeroReturnError)):
                    logger.error(error)
                if time != retry:
                    await asyncio.sleep(1)
                else:
                    raise error
                continue
            if response.status_code != 200:
                return None
            async with async_open(path, 'wb') as file:
                await file.write(response.content)
            return path.resolve()

    async def _get_from_enka(self, item: str) -> Optional[Path]:
        return None

    async def _get_from_honey(self, item: str) -> Optional[Path]:
        if item in self.url_map.keys():
            path = self.path.joinpath(f"{item}.png")
            url = SCRAPE_HOST.join(SCRAPE_HOST.join(f'/img/{self.url_map.get(item)}'))
            if (result := await self._download(str(url) + '.png', path)) is not None:
                return result
            else:
                path = self.path.joinpath(f"{item}.webp")
                return await self._download(str(url) + '.webp', path)

    async def _get_img(self, overwrite: bool = False, *, item: str) -> Optional[Path]:
        path = next(filter(lambda x: x.stem == item, self.path.iterdir()), None)
        if not overwrite and path:
            return path.resolve()
        if overwrite and path is not None and path.exists():
            await async_remove(path)
        if (path := await self._get_from_enka(item)) is not None:
            return path
        else:
            return await self._get_from_honey(item)

    def __getattr__(self, item: str):
        if item in self.icon_types:
            return partial(self._get_img, item=item)
        else:
            object.__getattribute__(self, item)

    def __del__(self) -> None:
        with self._lock:
            if self._client is not None and not self._client.is_closed:
                self._client.aclose()
                del self._client


class _CharacterAssets(_AssetsService):
    enka: Optional[EnkaCharacterAsset]

    side: ICON_TYPE
    card: ICON_TYPE
    banner: ICON_TYPE
    gacha: ICON_TYPE

    @cached_property
    def honey_id(self) -> str:
        return f"{HONEY_DATA['character'].get(str(self.id), '')[0]}_{str(self.id)[-3:]}"

    @cached_property
    def enka(self) -> Optional[EnkaCharacterAsset]:
        api = getattr(self, '_enka_api', None)
        cid = getattr(self, 'id', None)
        if api is None or cid is None:
            return None
        return api.character(cid)

    def __init__(self, client: Optional[AsyncClient] = None, enka: Optional[EnkaAssets] = None):
        super().__init__(client)
        self._enka_api = enka or EnkaAssets()

    def __call__(self, target: int) -> "_CharacterAssets":
        result = _CharacterAssets(self.client)
        result.id = target
        result._enka_api = self._enka_api
        return result

    async def _get_from_enka(self, item: str) -> Optional[Path]:
        # noinspection PyUnboundLocalVariable
        if (
                self.enka is not None
                and
                item in (data := self.enka.images.dict()).keys()
                and
                (url := data[item]['url'])
        ):
            path = self.path.joinpath(f"{item}.png")
            return await self._download(url, path)

    @cached_property
    def url_map(self) -> Dict[str, str]:
        return {
            'icon': f"{self.honey_id}_icon",
            'side': f"{self.honey_id}_side_icon",
            'banner': f"{self.honey_id}_gacha_splash",
            'gacha': f"{self.honey_id}_gacha_card",
        }


class _WeaponAssets(_AssetsService):
    awakened: ICON_TYPE
    gacha: ICON_TYPE

    @cached_property
    def honey_id(self) -> str:
        return f"i_n{self.id}"

    @cached_property
    def url_map(self) -> Dict[str, str]:
        return {
            'icon': f'{self.honey_id}',
            'awakened': f'{self.honey_id}_awaken_icon',
            'gacha': f'{self.honey_id}_gacha_icon',
        }

    async def _get_from_enka(self, item: str) -> Optional[Path]:
        if (icon_name := weapon_to_icon_name(self.id)) is not None and item in ['icon', 'awakened']:
            file_name = [
                ENKA_HOST.join(f"UI_EquipIcon_{icon_name}.png"),
                ENKA_HOST.join(f"UI_EquipIcon_{icon_name}_Awaken.png")
            ]
            url = file_name[['icon', 'awakened'].index(item)]
            path = self.path.joinpath(f"{item}.png")
            return await self._download(url, path)


class _MaterialAssets(_AssetsService):
    @cached_property
    def honey_id(self) -> str:
        return HONEY_DATA['material'].get(str(self.id), '')[0]

    @cached_property
    def url_map(self) -> Dict[str, str]:
        return {'icon': f"{self.honey_id}.webp"}

    async def _get_from_honey(self, item: str) -> Optional[Path]:
        path = self.path.joinpath(f"{item}.webp")
        url = SCRAPE_HOST.join(f'/img/{self.url_map.get(item)}')
        return await self._download(url, path)


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
        self.character = _CharacterAssets()
        self.weapon = _WeaponAssets()
        self.material = _MaterialAssets()


AssetsServiceType = TypeVar('AssetsServiceType', bound=_AssetsService)
