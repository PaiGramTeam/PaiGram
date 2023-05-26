"""用于下载和管理角色、武器、材料等的图标"""
from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from functools import cached_property, lru_cache, partial
from multiprocessing import RLock as Lock
from pathlib import Path
from ssl import SSLZeroReturnError
from typing import AsyncIterator, Awaitable, Callable, ClassVar, Dict, Optional, TYPE_CHECKING, TypeVar, Union

from aiofiles import open as async_open
from aiofiles.os import remove as async_remove
from enkanetwork import Assets as EnkaAssets
from enkanetwork.model.assets import CharacterAsset as EnkaCharacterAsset
from httpx import AsyncClient, HTTPError, HTTPStatusError, TransportError, URL
from typing_extensions import Self

from core.base_service import BaseService
from core.config import config
from metadata.genshin import AVATAR_DATA, HONEY_DATA, MATERIAL_DATA, NAMECARD_DATA, WEAPON_DATA
from metadata.scripts.honey import update_honey_metadata
from metadata.scripts.metadatas import update_metadata_from_ambr, update_metadata_from_github
from metadata.shortname import roleToId, weaponToId
from modules.wiki.base import HONEY_HOST
from utils.const import AMBR_HOST, ENKA_HOST, PROJECT_ROOT
from utils.log import logger
from utils.typedefs import StrOrInt, StrOrURL

if TYPE_CHECKING:
    from httpx import Response
    from multiprocessing.synchronize import RLock

__all__ = ("AssetsServiceType", "AssetsService", "AssetsServiceError", "AssetsCouldNotFound", "DEFAULT_EnkaAssets")

ICON_TYPE = Union[Callable[[bool], Awaitable[Optional[Path]]], Callable[..., Awaitable[Optional[Path]]]]
NAME_MAP_TYPE = Dict[str, StrOrURL]

ASSETS_PATH = PROJECT_ROOT.joinpath("resources/assets")
ASSETS_PATH.mkdir(exist_ok=True, parents=True)

DATA_MAP = {"avatar": AVATAR_DATA, "weapon": WEAPON_DATA, "material": MATERIAL_DATA}

DEFAULT_EnkaAssets = EnkaAssets(lang="chs")


class AssetsServiceError(Exception):
    pass


class AssetsCouldNotFound(AssetsServiceError):
    def __init__(self, message: str, target: str):
        self.message = message
        self.target = target
        super().__init__(f"{message}: target={message}")


class _AssetsService(ABC):
    _lock: ClassVar["RLock"] = Lock()
    _dir: ClassVar[Path]
    icon_types: ClassVar[list[str]]

    _client: Optional[AsyncClient] = None
    _links: dict[str, str] = {}

    id: int
    type: str

    icon: ICON_TYPE
    """图标"""

    @abstractmethod
    @cached_property
    def game_name(self) -> str:
        """游戏数据中的名称"""

    @cached_property
    def honey_id(self) -> str:
        """当前资源在 Honey Impact 所对应的 ID"""
        return HONEY_DATA[self.type].get(str(self.id), [""])[0]

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
        """用于生成与 target 对应的 assets"""
        result = self.__class__(self.client)
        result.id = target
        return result

    def __init_subclass__(cls, **kwargs) -> None:
        """初始化一些类变量"""
        from itertools import chain

        cls.icon_types = [  # 支持的图标类型
            k
            for k, v in chain(cls.__annotations__.items(), *map(lambda x: x.__annotations__.items(), cls.__bases__))
            if v in [ICON_TYPE, "ICON_TYPE"]
        ]
        cls.type = cls.__name__.lstrip("_").split("Assets")[0].lower()  # 当前 assert 的类型
        cls._dir = ASSETS_PATH.joinpath(cls.type)  # 图标保存的文件夹
        cls._dir.mkdir(exist_ok=True, parents=True)

    async def _request(self, url: str, interval: float = 0.2) -> "Response":
        error = None
        for _ in range(5):
            try:
                response = await self.client.get(url, follow_redirects=False)
                if response.headers["content-length"] == "2358":
                    continue
                return response
            except (TransportError, SSLZeroReturnError) as e:
                error = e
                await asyncio.sleep(interval)
                continue
        if error is not None:
            raise error

    async def _download(self, url: StrOrURL, path: Path, retry: int = 5) -> Path | None:
        """从 url 下载图标至 path"""
        logger.debug("正在从 %s 下载图标至 %s", url, path)
        headers = None
        if config.enka_network_api_agent is not None and URL(url).host == "enka.network":
            headers = {"user-agent": config.enka_network_api_agent}
        for time in range(retry):
            try:
                response = await self.client.get(url, follow_redirects=False, headers=headers)
            except Exception as error:  # pylint: disable=W0703
                if not isinstance(error, (HTTPError, SSLZeroReturnError)):
                    logger.error(error)  # 打印未知错误
                if time != retry - 1:  # 未达到重试次数
                    await asyncio.sleep(1)
                else:
                    raise error
                continue
            if response.status_code != 200:  # 判定页面是否正常
                return None
            async with async_open(path, "wb") as file:
                await file.write(response.content)  # 保存图标
            return path.resolve()

    async def _get_from_ambr(self, item: str) -> AsyncIterator[str | None]:  # pylint: disable=W0613,R0201
        """从 ambr.top 上获取目标链接"""
        yield None

    async def _get_from_enka(self, item: str) -> AsyncIterator[str | None]:  # pylint: disable=W0613,R0201
        """从 enke.network 上获取目标链接"""
        yield None

    async def _get_from_honey(self, item: str) -> AsyncIterator[str | None]:
        """从 honey 上获取目标链接"""
        if (honey_name := self.honey_name_map.get(item, None)) is not None:
            yield HONEY_HOST.join(f"img/{honey_name}.png")
            yield HONEY_HOST.join(f"img/{honey_name}.webp")

    async def _download_url_generator(self, item: str) -> AsyncIterator[str]:
        # 获取当前 `AssetsService` 的所有爬虫
        for func in map(lambda x: getattr(self, x), sorted(filter(lambda x: x.startswith("_get_from_"), dir(self)))):
            async for url in func(item):
                if url is not None:
                    try:
                        if (response := await self._request(url := str(url))) is None:
                            continue
                        response.raise_for_status()
                        yield url
                    except HTTPStatusError:
                        continue

    async def _get_download_url(self, item: str) -> str | None:
        """获取图标的下载链接"""
        async for url in self._download_url_generator(item):
            if url is not None:
                return url

    async def _get_img(self, overwrite: bool = False, *, item: str) -> Path | None:
        """获取图标"""
        path = next(filter(lambda x: x.stem == item, self.path.iterdir()), None)
        if not overwrite and path:  # 如果需要下载的图标存在且不覆盖( overwrite )
            return path.resolve()
        if path is not None and path.exists():
            if overwrite:  # 如果覆盖
                await async_remove(path)  # 删除已存在的图标
            else:
                return path
        # 依次从使用当前 assets class 中的爬虫下载图标，顺序为爬虫名的字母顺序
        async for url in self._download_url_generator(item):
            if url is not None:
                path = self.path.joinpath(f"{item}{Path(url).suffix}")
                if (result := await self._download(url, path)) is not None:
                    return result

    @lru_cache
    async def get_link(self, item: str) -> str | None:
        """获取相应图标链接"""
        return await self._get_download_url(item)

    def __getattr__(self, item: str):
        """魔法"""
        if item in self.icon_types:
            return partial(self._get_img, item=item)
        object.__getattribute__(self, item)
        return None

    @abstractmethod
    @cached_property
    def game_name_map(self) -> dict[str, str]:
        """游戏中的图标名"""

    @abstractmethod
    @cached_property
    def honey_name_map(self) -> dict[str, str]:
        """来自honey的图标名"""


class _AvatarAssets(_AssetsService):
    enka: EnkaCharacterAsset | None

    side: ICON_TYPE
    """侧视图图标"""

    card: ICON_TYPE
    """卡片图标"""

    gacha: ICON_TYPE
    """抽卡立绘"""

    gacha_card: ICON_TYPE
    """抽卡卡片"""

    @cached_property
    def game_name(self) -> str:
        icon = "UI_AvatarIcon_"
        if (avatar := AVATAR_DATA.get(str(self.id), None)) is not None:
            icon = avatar["icon"]
        else:
            for aid, avatar in AVATAR_DATA.items():
                if aid.startswith(str(self.id)):
                    icon = avatar["icon"]
        return re.findall(r"UI_AvatarIcon_(.*)", icon)[0]

    @cached_property
    def honey_id(self) -> str:
        return HONEY_DATA["avatar"].get(str(self.id), "")[0]

    @cached_property
    def enka(self) -> Optional[EnkaCharacterAsset]:
        api = getattr(self, "_enka_api", None)
        cid = getattr(self, "id", None)
        return None if api is None or cid is None else api.character(cid)

    def __init__(self, client: Optional[AsyncClient] = None, enka: Optional[EnkaAssets] = None):
        super().__init__(client)
        self._enka_api = enka or DEFAULT_EnkaAssets

    def __call__(self, target: StrOrInt) -> "_AvatarAssets":
        temp = target
        result = _AvatarAssets(self.client)
        if isinstance(target, str):
            try:
                target = int(target)
            except ValueError:
                target = roleToId(target)
        if isinstance(target, str) or target is None:
            raise AssetsCouldNotFound("找不到对应的角色", temp)
        result.id = target
        result._enka_api = self._enka_api
        return result

    async def _get_from_ambr(self, item: str) -> AsyncIterator[str | None]:
        if item in {"icon", "side", "gacha"}:
            yield str(AMBR_HOST.join(f"assets/UI/{self.game_name_map[item]}.png"))

    async def _get_from_enka(self, item: str) -> AsyncIterator[str | None]:
        if (item_id := self.game_name_map.get(item)) is not None:
            yield str(ENKA_HOST.join(f"ui/{item_id}.png"))

    @cached_property
    def honey_name_map(self) -> dict[str, str]:
        return {
            "icon": f"{self.honey_id}_icon",
            "side": f"{self.honey_id}_side_icon",
            "gacha": f"{self.honey_id}_gacha_splash",
            "gacha_card": f"{self.honey_id}_gacha_card",
        }

    @cached_property
    def game_name_map(self) -> dict[str, str]:
        return {
            "icon": f"UI_AvatarIcon_{self.game_name}",
            "card": f"UI_AvatarIcon_{self.game_name}_Card",
            "side": f"UI_AvatarIcon_Side_{self.game_name}",
            "gacha": f"UI_Gacha_AvatarImg_{self.game_name}",
        }


class _WeaponAssets(_AssetsService):
    awaken: ICON_TYPE
    """突破后图标"""

    gacha: ICON_TYPE
    """抽卡立绘"""

    @cached_property
    def game_name(self) -> str:
        return re.findall(r"UI_EquipIcon_(.*)", WEAPON_DATA[str(self.id)]["icon"])[0]

    @cached_property
    def game_name_map(self) -> dict[str, str]:
        return {
            "icon": f"UI_EquipIcon_{self.game_name}",
            "awaken": f"UI_EquipIcon_{self.game_name}_Awaken",
            "gacha": f"UI_Gacha_EquipIcon_{self.game_name}",
        }

    @cached_property
    def honey_id(self) -> str:
        return f"i_n{self.id}"

    def __call__(self, target: StrOrInt) -> Self:
        temp = target
        result = _WeaponAssets(self.client)
        if isinstance(target, str):
            target = int(target) if target.isnumeric() else weaponToId(target)
        if isinstance(target, str) or target is None:
            raise AssetsCouldNotFound("找不到对应的武器", temp)
        result.id = target
        return result

    async def _get_from_ambr(self, item: str) -> AsyncIterator[str | None]:
        if item == "icon":
            yield str(AMBR_HOST.join(f"assets/UI/{self.game_name_map.get(item)}.png"))

    async def _get_from_enka(self, item: str) -> AsyncIterator[str | None]:
        if item in self.game_name_map:
            yield str(ENKA_HOST.join(f"ui/{self.game_name_map.get(item)}.png"))

    @cached_property
    def honey_name_map(self) -> dict[str, str]:
        return {
            "icon": f"{self.honey_id}",
            "awaken": f"{self.honey_id}_awaken_icon",
            "gacha": f"{self.honey_id}_gacha_icon",
        }


class _MaterialAssets(_AssetsService):
    @cached_property
    def game_name(self) -> str:
        return str(self.id)

    @cached_property
    def game_name_map(self) -> dict[str, str]:
        return {"icon": f"UI_ItemIcon_{self.game_name}"}

    @cached_property
    def honey_name_map(self) -> dict[str, str]:
        return {"icon": self.honey_id}

    def __call__(self, target: StrOrInt) -> Self:
        temp = target
        result = _MaterialAssets(self.client)
        if isinstance(target, str):
            if target.isnumeric():
                target = int(target)
            else:
                target = {v["name"]: int(k) for k, v in MATERIAL_DATA.items()}.get(target)
        if isinstance(target, str) or target is None:
            raise AssetsCouldNotFound("找不到对应的素材", temp)
        result.id = target
        return result

    async def _get_from_ambr(self, item: str) -> AsyncIterator[str | None]:
        if item == "icon":
            yield str(AMBR_HOST.join(f"assets/UI/{self.game_name_map.get(item)}.png"))

    async def _get_from_honey(self, item: str) -> AsyncIterator[str | None]:
        yield HONEY_HOST.join(f"/img/{self.honey_name_map.get(item)}.png")
        yield HONEY_HOST.join(f"/img/{self.honey_name_map.get(item)}.webp")


class _ArtifactAssets(_AssetsService):
    flower: ICON_TYPE
    """生之花"""

    plume: ICON_TYPE
    """死之羽"""

    sands: ICON_TYPE
    """时之沙"""

    goblet: ICON_TYPE
    """空之杯"""

    circlet: ICON_TYPE
    """理之冠"""

    @cached_property
    def honey_id(self) -> str:
        return HONEY_DATA["artifact"][str(self.id)][0]

    @cached_property
    def game_name(self) -> str:
        return f"UI_RelicIcon_{self.id}"

    async def _get_from_enka(self, item: str) -> AsyncIterator[str | None]:
        if item in self.game_name_map:
            yield str(ENKA_HOST.join(f"ui/{self.game_name_map.get(item)}.png"))

    async def _get_from_ambr(self, item: str) -> AsyncIterator[str | None]:
        if item in self.game_name_map:
            yield str(AMBR_HOST.join(f"assets/UI/reliquary/{self.game_name_map[item]}.png"))

    @cached_property
    def game_name_map(self) -> dict[str, str]:
        return {
            "icon": f"UI_RelicIcon_{self.id}_4",
            "flower": f"UI_RelicIcon_{self.id}_4",
            "plume": f"UI_RelicIcon_{self.id}_2",
            "sands": f"UI_RelicIcon_{self.id}_5",
            "goblet": f"UI_RelicIcon_{self.id}_1",
            "circlet": f"UI_RelicIcon_{self.id}_3",
        }

    @cached_property
    def honey_name_map(self) -> dict[str, str]:
        first_id = int(re.findall(r"\d+", HONEY_DATA["artifact"][str(self.id)][-1])[0])
        return {
            "icon": f"i_n{first_id + 30}",
            "flower": f"i_n{first_id + 30}",
            "plume": f"i_n{first_id + 10}",
            "sands": f"i_n{first_id + 40}",
            "goblet": f"i_n{first_id}",
            "circlet": f"i_n{first_id + 20}",
        }


class _NamecardAssets(_AssetsService):
    enka: EnkaCharacterAsset | None

    navbar: ICON_TYPE
    """好友名片背景"""

    profile: ICON_TYPE
    """个人资料名片背景"""

    @cached_property
    def honey_id(self) -> str:
        return HONEY_DATA["namecard"][str(self.id)][0]

    @cached_property
    def game_name(self) -> str:
        return NAMECARD_DATA[str(self.id)]["icon"]

    @lru_cache
    def _get_id_from_avatar_id(self, avatar_id: Union[int, str]) -> int:
        avatar_icon_name = AVATAR_DATA[str(avatar_id)]["icon"].replace("AvatarIcon", "NameCardIcon")
        for namecard_id, namecard_data in NAMECARD_DATA.items():
            if namecard_data["icon"] == avatar_icon_name:
                return int(namecard_id)
        raise ValueError(avatar_id)

    def __call__(self, target: int) -> "_NamecardAssets":
        result = _NamecardAssets(self.client)
        target = int(target) if not isinstance(target, int) else target
        if target > 10000000:
            target = self._get_id_from_avatar_id(target)
        result.id = target
        result.enka = DEFAULT_EnkaAssets.namecards(target)
        return result

    async def _get_from_ambr(self, item: str) -> AsyncIterator[str | None]:
        if item == "profile":
            yield AMBR_HOST.join(f"assets/UI/namecard/{self.game_name_map[item]}.png.png")

    async def _get_from_enka(self, item: str) -> AsyncIterator[str | None]:
        if (url := getattr(self.enka, {"profile": "banner"}.get(item, item), None)) is not None:
            yield url.url

    @cached_property
    def game_name_map(self) -> dict[str, str]:
        return {
            "icon": self.game_name,
            "navbar": NAMECARD_DATA[str(self.id)]["navbar"],
            "profile": NAMECARD_DATA[str(self.id)]["profile"],
        }

    @cached_property
    def honey_name_map(self) -> dict[str, str]:
        return {
            "icon": self.honey_id,
            "navbar": f"{self.honey_id}_back",
            "profile": f"{self.honey_id}_profile",
        }


class AssetsService(BaseService.Dependence):
    """asset服务

    用于储存和管理 asset :
        当对应的 asset (如某角色图标)不存在时，该服务会先查找本地。
        若本地不存在，则从网络上下载；若存在，则返回其路径
    """

    avatar: _AvatarAssets
    """角色"""

    weapon: _WeaponAssets
    """武器"""

    material: _MaterialAssets
    """素材"""

    artifact: _ArtifactAssets
    """圣遗物"""

    namecard: _NamecardAssets
    """名片"""

    def __init__(self):
        for attr, assets_type_name in filter(
            lambda x: (not x[0].startswith("_")) and x[1].endswith("Assets"), self.__annotations__.items()
        ):
            setattr(self, attr, globals()[assets_type_name]())

    async def initialize(self) -> None:  # pylint: disable=R0201
        """启动 AssetsService 服务，刷新元数据"""
        logger.info("正在刷新元数据")
        # todo 这3个任务同时异步下载
        await update_metadata_from_github(False)
        await update_metadata_from_ambr(False)
        await update_honey_metadata(False)
        logger.info("刷新元数据成功")


AssetsServiceType = TypeVar("AssetsServiceType", bound=_AssetsService)
