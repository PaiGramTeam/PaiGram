from __future__ import annotations

from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import Awaitable, Callable, ClassVar, TypeVar

from enkanetwork import Assets as EnkaAssets
from enkanetwork.model.assets import CharacterAsset as EnkaCharacterAsset
from httpx import AsyncClient
from typing_extensions import Self

from core.base_service import BaseService
from utils.typedefs import StrOrInt

__all__ = ("AssetsServiceType", "AssetsService", "AssetsServiceError", "AssetsCouldNotFound", "DEFAULT_EnkaAssets")

ICON_TYPE = Callable[[bool], Awaitable[Path | None]] | Callable[..., Awaitable[Path | None]]
DEFAULT_EnkaAssets: EnkaAssets
_GET_TYPE = partial | list[str] | int | str | ICON_TYPE | Path | AsyncClient | None | Self | dict[str, str]

class AssetsServiceError(Exception): ...

class AssetsCouldNotFound(AssetsServiceError):
    message: str
    target: str
    def __init__(self, message: str, target: str): ...

class _AssetsService(ABC):
    icon_types: ClassVar[list[str]]
    id: int
    type: str

    icon: ICON_TYPE
    """图标"""

    @abstractmethod
    @property
    def game_name(self) -> str:
        """游戏数据中的名称"""
    @property
    def honey_id(self) -> str:
        """当前资源在 Honey Impact 所对应的 ID"""
    @property
    def path(self) -> Path:
        """当前资源的文件夹"""
    @property
    def client(self) -> AsyncClient:
        """当前的 http client"""
    def __init__(self, client: AsyncClient | None = None) -> None: ...
    def __call__(self, target: int) -> Self:
        """用于生成与 target 对应的 assets"""
    def __getattr__(self, item: str) -> _GET_TYPE:
        """魔法"""
    async def get_link(self, item: str) -> str | None:
        """获取相应图标链接"""
    @abstractmethod
    @property
    def game_name_map(self) -> dict[str, str]:
        """游戏中的图标名"""
    @abstractmethod
    @property
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

    @property
    def honey_name_map(self) -> dict[str, str]: ...
    @property
    def game_name_map(self) -> dict[str, str]: ...
    @property
    def enka(self) -> EnkaCharacterAsset | None: ...
    def __init__(self, client: AsyncClient | None = None, enka: EnkaAssets | None = None) -> None: ...
    def __call__(self, target: StrOrInt) -> Self: ...
    def __getitem__(self, item: str) -> _GET_TYPE | EnkaCharacterAsset: ...
    def game_name(self) -> str: ...

class _WeaponAssets(_AssetsService):
    awaken: ICON_TYPE
    """突破后图标"""

    gacha: ICON_TYPE
    """抽卡立绘"""

    @property
    def honey_name_map(self) -> dict[str, str]: ...
    @property
    def game_name_map(self) -> dict[str, str]: ...
    def __call__(self, target: StrOrInt) -> Self: ...
    def game_name(self) -> str: ...

class _MaterialAssets(_AssetsService):
    @property
    def honey_name_map(self) -> dict[str, str]: ...
    @property
    def game_name_map(self) -> dict[str, str]: ...
    def __call__(self, target: StrOrInt) -> Self: ...
    def game_name(self) -> str: ...

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

    @property
    def honey_name_map(self) -> dict[str, str]: ...
    @property
    def game_name_map(self) -> dict[str, str]: ...
    def game_name(self) -> str: ...

class _NamecardAssets(_AssetsService):
    enka: EnkaCharacterAsset | None

    navbar: ICON_TYPE
    """好友名片背景"""

    profile: ICON_TYPE
    """个人资料名片背景"""

    @property
    def honey_name_map(self) -> dict[str, str]: ...
    @property
    def game_name_map(self) -> dict[str, str]: ...
    def game_name(self) -> str: ...

class AssetsService(BaseService.Dependence):
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

AssetsServiceType = TypeVar("AssetsServiceType", bound=_AssetsService)
